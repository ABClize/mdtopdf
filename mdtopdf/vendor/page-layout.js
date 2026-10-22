options => {
  const {action = 'measure', layouts = []} = options || {};
  // Resolve page descriptors from the browser's parsed CSS, including imports
  // and active print media. Keep physical page geometry separate from diagrams.
  const warnings = [];
  const rules = [];
  const collect = sheet => {
    let children;
    try { children = sheet.cssRules; } catch { return; }
    for (const rule of children) {
      if (rule.type === CSSRule.PAGE_RULE) rules.push(rule);
      else if (rule.type === CSSRule.IMPORT_RULE) {
        if (!rule.media.mediaText || matchMedia(rule.media.mediaText).matches) collect(rule.styleSheet);
      } else if (rule.cssRules) {
        if (rule.type === CSSRule.MEDIA_RULE && !matchMedia(rule.conditionText).matches) continue;
        if (rule.type === CSSRule.SUPPORTS_RULE && !CSS.supports(rule.conditionText)) continue;
        collect(rule);
      }
    }
  };
  for (const sheet of document.styleSheets) {
    if (!sheet.disabled && (!sheet.media.mediaText || matchMedia(sheet.media.mediaText).matches)) collect(sheet);
  }
  const root = document.documentElement;
  const probe = document.createElement('div');
  probe.style.cssText = 'all:initial;position:fixed;visibility:hidden;pointer-events:none;left:-100000px;top:0';
  const ruler = document.createElement('div');
  ruler.style.cssText = 'all:initial;display:block;box-sizing:content-box;font:inherit';
  probe.appendChild(ruler);
  document.body.appendChild(probe);
  // Playwright's paper fallback is Letter when CSS size is auto/unspecified.
  const papers = {a3:[297,420], a4:[210,297], a5:[148,210], b4:[250,353], b5:[176,250],
    'jis-b4':[257,364], 'jis-b5':[182,257], letter:[215.9,279.4], legal:[215.9,355.6], ledger:[279.4,431.8]};
  const length = (value, axis, fallback = 0) => {
    if (!value || ['auto', 'none', 'normal'].includes(value)) return fallback;
    ruler.style[axis] = '0px';
    ruler.style[axis] = value;
    const result = parseFloat(getComputedStyle(ruler)[axis]);
    return Number.isFinite(result) ? result : fallback;
  };
  const tokens = value => {
    const parts = [];
    let part = '', depth = 0;
    for (const character of value) {
      if (/\s/.test(character) && !depth) {
        if (part) parts.push(part);
        part = '';
      } else {
        part += character;
        if (character === '(') depth++;
        else if (character === ')') depth--;
      }
    }
    if (part) parts.push(part);
    return parts;
  };
  const shorthandFor = (style, property) => {
    const candidates = property.startsWith('margin-') ? ['margin']
      : property.startsWith('padding-') ? ['padding']
      : property.startsWith('border-') ? [property.split('-').slice(0, 2).join('-'), `border-${property.split('-')[2]}`, 'border']
      : property.startsWith('font-') || property === 'line-height' ? ['font'] : [];
    return candidates.find(name => style.getPropertyValue(name)) || null;
  };
  const cascade = (name, side, first) => {
    const chosen = new Map();
    for (const rule of rules) {
      for (const selector of (rule.selectorText || '').split(',')) {
        const parts = selector.trim().split(':');
        const pageName = parts.shift();
        if (pageName && pageName !== name) continue;
        if (parts.some(p => p === 'blank' || (p === 'first' ? !first : p !== side))) continue;
        const specificity = (pageName ? 100 : 0) + (parts.includes('first') ? 10 : 0) + parts.filter(p => p === 'left' || p === 'right').length;
        for (const property of rule.style) {
          const rank = specificity + (rule.style.getPropertyPriority(property) ? 1000 : 0);
          if (!chosen.has(property) || chosen.get(property).rank <= rank) {
            const raw = rule.style.getPropertyValue(property);
            // var() shorthands have empty longhands until substitution. Retain
            // their original shorthand and let CSSOM expand it after resolving.
            const shorthand = raw ? null : shorthandFor(rule.style, property);
            chosen.set(property, {value: raw || (shorthand && rule.style.getPropertyValue(shorthand)), shorthand, rank});
          }
        }
      }
    }
    return chosen;
  };
  const dimensions = descriptors => {
    for (const property of [...probe.style]) if (property.startsWith('--')) probe.style.removeProperty(property);
    for (const [property, item] of descriptors) if (property.startsWith('--')) probe.style.setProperty(property, item.value);
    const value = (property, fallback = '') => {
      const item = descriptors.get(property);
      const raw = item?.value || fallback;
      // CSS-wide keywords on custom properties resolve differently from the
      // font/length properties they describe, so do not route them through one.
      if (['inherit', 'initial', 'unset', 'revert', 'revert-layer'].includes(raw)) return raw;
      probe.style.setProperty('--mdtopdf-measure-value', raw);
      const resolved = getComputedStyle(probe).getPropertyValue('--mdtopdf-measure-value').trim();
      if (!item?.shorthand) return resolved;
      const declaration = document.createElement('div').style;
      declaration.setProperty(item.shorthand, resolved);
      return declaration.getPropertyValue(property);
    };
    // Page font properties inherit from the document root. Resolve a relative
    // page font size against that inherited size before measuring em/ch/ex.
    const rootStyle = getComputedStyle(root);
    for (const property of ['font-family', 'font-size', 'font-weight', 'font-style', 'line-height']) {
      probe.style.setProperty(property, rootStyle.getPropertyValue(property));
    }
    ruler.style.fontSize = value('font-size', 'inherit');
    const pageFontSize = getComputedStyle(ruler).fontSize;
    ruler.style.fontSize = 'inherit';
    probe.style.fontSize = pageFontSize;
    for (const property of ['font-family', 'font-weight', 'font-style', 'line-height']) {
      if (descriptors.has(property)) probe.style.setProperty(property, value(property));
    }
    const size = tokens(value('size', 'auto').toLowerCase());
    const named = size.find(part => papers[part]);
    let [width, height] = (papers[named || 'letter']).map(mm => mm * 96 / 25.4);
    probe.style.width = `${width}px`;
    probe.style.height = `${height}px`;
    if (size[0] && !named && !['auto', 'portrait', 'landscape'].includes(size[0])) {
      width = length(size[0], 'width', width);
      height = length(size[1] || size[0], 'height', height);
    }
    if (size.includes('landscape')) [width, height] = [Math.max(width, height), Math.min(width, height)];
    if (size.includes('portrait')) [width, height] = [Math.min(width, height), Math.max(width, height)];
    probe.style.width = `${width}px`;
    probe.style.height = `${height}px`;
    const inset = side => {
      const axis = ['left', 'right'].includes(side) ? 'width' : 'height';
      const margin = length(value(`margin-${side}`), axis);
      const padding = length(value(`padding-${side}`), axis);
      const border = ['none', 'hidden', ''].includes(value(`border-${side}-style`)) ? 0 : length(value(`border-${side}-width`), axis);
      return margin + padding + border;
    };
    return {width: width - inset('left') - inset('right'), height: height - inset('top') - inset('bottom')};
  };
  // Styles and page names stay fixed during this measurement pass. Documents
  // with many diagrams can reuse the same resolved paper area within the call.
  const pageAreas = new Map();
  const geometry = name => {
    if (pageAreas.has(name)) return pageAreas.get(name);
    // Before pagination the page index is unknown. Use the narrowest/shortest
    // matching page area so first/left/right page styles cannot clip a diagram.
    const variants = ['left', 'right'].flatMap(side => [false, true].map(first => dimensions(cascade(name, side, first))));
    const area = {width: Math.min(...variants.map(p => p.width)), height: Math.min(...variants.map(p => p.height))};
    if (!(area.width > 0 && area.height > 0)) throw new Error('Page margins leave no printable area for diagrams.');
    pageAreas.set(name, area);
    return area;
  };
  const pageName = element => {
    for (let node = element; node; node = node.parentElement) {
      const name = getComputedStyle(node).page;
      if (name && name !== 'auto') return name;
    }
    return '';
  };
  const atWidth = (width, operation) => {
    const old = root.style.getPropertyValue('width');
    const priority = root.style.getPropertyPriority('width');
    root.style.setProperty('width', `${width}px`, 'important');
    try { return operation(); } finally {
      if (old) root.style.setProperty('width', old, priority);
      else root.style.removeProperty('width');
    }
  };
  try {
    const main = document.querySelector('main.document');
    const primary = geometry(pageName(main));
    if (action === 'measure') return primary;
    const figures = [...document.querySelectorAll('figure.mermaid-diagram')];
    if (action === 'prepare') {
      return figures.map(element => {
        const area = geometry(pageName(element));
        return atWidth(area.width, () => {
          const style = getComputedStyle(element);
          return {page_width: area.width,
            width: Math.max(1, element.clientWidth - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight)),
            height: Math.max(1, area.height - parseFloat(style.marginTop) - parseFloat(style.marginBottom)
              - parseFloat(style.paddingTop) - parseFloat(style.paddingBottom)
              - parseFloat(style.borderTopWidth) - parseFloat(style.borderBottomWidth)),
            source_line: Number(element.dataset.mdtopdfSourceLine) || null};
        });
      });
    }
    for (const [index, element] of figures.entries()) {
      const svg = element.querySelector('svg.pele');
      const layout = layouts[index];
      if (!svg || !layout) continue;
      atWidth(layout.page_width, () => {
        const style = getComputedStyle(svg);
        const cap = (value, pixels) => value === 'none' ? `${pixels}px` : `min(${value}, ${pixels}px)`;
        svg.style.maxWidth = cap(style.maxWidth, layout.width);
        svg.style.maxHeight = cap(style.maxHeight, layout.height);
        const threshold = length(getComputedStyle(element).getPropertyValue('--mdtopdf-diagram-min-font-size').trim() || '8pt', 'height') * 0.75;
        const sizes = [];
        for (const text of svg.querySelectorAll('text, math')) {
          if (!text.textContent.trim() || !text.getBoundingClientRect().width) continue;
          const matrix = (text.getScreenCTM ? text : text.closest('foreignObject'))?.getScreenCTM();
          if (matrix) sizes.push(parseFloat(getComputedStyle(text).fontSize) * Math.hypot(matrix.a, matrix.b) * 0.75);
        }
        const smallest = Math.min(...sizes);
        if (smallest + 0.1 < threshold) {
          warnings.push({type:'diagram_text_too_small',
            message:`Diagram ${index + 1} text is approximately ${smallest.toFixed(1)}pt on the page (minimum ${threshold.toFixed(1)}pt). Use a wider page, larger diagram font, or split the diagram.`,
            diagram_index:index + 1, ...(layout.source_line ? {source_line:layout.source_line} : {}),
            font_size_pt:Math.round(smallest * 10) / 10, minimum_font_size_pt:threshold});
        }
      });
    }
    return warnings;
  } finally { probe.remove(); }
}
