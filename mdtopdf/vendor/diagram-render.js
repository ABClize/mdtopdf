async (layouts = []) => {
  const warnings = [];
  const decode = value => new TextDecoder().decode(Uint8Array.from(atob(value), c => c.charCodeAt(0)));
  const failure = (error, element, source, index) => {
    const details = {
      code: error.code || 'render',
      message: error.message || String(error),
      diagram_index: index + 1,
    };
    if (error.type) details.diagram_type = error.type;
    if (error.mermaidType) details.mermaid_type = error.mermaidType;
    if (error.line > 0) details.renderer_line = error.line;
    if (error.column > 0) details.renderer_column = error.column;
    const sourceStart = Number(element.dataset.mdtopdfSourceLine);
    if (sourceStart > 0) details.source_start_line = sourceStart;
    const lines = source.replace(/\r\n?/g, '\n').split('\n');
    const snippet = error.snippet || '';
    const excerpt = snippet.split('\n')[0];
    // Pele preprocesses frontmatter, directives and comments before parsing.
    // Its parser line numbers are therefore not always input line numbers.
    // Map only an unambiguous original excerpt, retaining the renderer's own
    // location separately when mapping cannot be proved.
    if (excerpt.trim()) {
      const matches = lines.map((line, i) => line === excerpt ? i : -1).filter(i => i >= 0);
      if (matches.length === 1) {
        details.diagram_line = matches[0] + 1;
        if (error.column > 0) details.diagram_column = error.column;
      }
    } else if (error.line > 0 && /(?:got ['"]?(?:\$end|EOF)|end of (?:input|file))/i.test(details.message)) {
      // An unfinished construct is reported at the synthetic EOF newline.
      // Anchor it to the end of the last source line, not a nonexistent line.
      let last = lines.length - 1;
      while (last > 0 && !lines[last].trim()) last--;
      details.diagram_line = last + 1;
      details.diagram_column = lines[last].length + 1;
      details.at_end = true;
    }
    if (details.diagram_line && sourceStart > 0) details.source_line = sourceStart + details.diagram_line - 1;
    details.snippet = details.at_end
      ? lines[details.diagram_line - 1] + '\n' + '-'.repeat(details.diagram_column - 1) + '^'
      : snippet || lines.slice(0, 5).join('\n');
    return {warnings, error: details};
  };
  const diagrams = [...document.querySelectorAll('[data-mdtopdf-mermaid]')];
  if (diagrams.length) await document.fonts.ready;
  for (const [index, element] of diagrams.entries()) {
    const source = decode(element.dataset.mdtopdfMermaid);
    let model;
    try {
      model = pele.parse(source);
    } catch (error) {
      return failure(error, element, source, index);
    }
    const idPrefix = `mdtopdfDiagram${index}`;
    // Resolve inherited variables and custom .pele rules before measuring.
    const probe = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    probe.setAttribute('class', `pele pele-${pele.detectType(source)} mermaid-rendered`);
    probe.style.cssText = 'position:absolute;visibility:hidden;width:0;height:0';
    element.appendChild(probe);
    const style = getComputedStyle(probe);
    const fontFamily = style.getPropertyValue('--pele-font').trim() || style.fontFamily;
    const fontFamilyMono = style.getPropertyValue('--pele-font-mono').trim() || 'monospace';
    const fontSize = parseFloat(style.fontSize);
    const theme = [...style].filter(name => name.startsWith('--pele-'))
      .map(name => [name, style.getPropertyValue(name)]);
    const mathProbe = document.createElement('div');
    mathProbe.style.cssText = 'position:absolute;left:-100000px;visibility:hidden;display:inline-block;white-space:nowrap';
    element.appendChild(mathProbe);
    const math = (tex, size) => {
      try {
        mathProbe.innerHTML = katex.renderToString(tex, {
          displayMode: true, throwOnError: true, trust: false, strict: 'ignore', output: 'mathml',
        });
        mathProbe.style.fontSize = `${size}px`;
        const expression = mathProbe.querySelector('math');
        // Measure the bare MathML exported in the SVG, without KaTeX scaling.
        mathProbe.replaceChildren(expression);
        expression.style.fontSize = `${size}px`;
        const {width, height} = expression.getBoundingClientRect();
        return {html: expression.outerHTML, width, height};
      } catch (error) {
        warnings.push({
          type: 'math_fallback', message: 'KaTeX could not render a diagram formula; source is shown.',
          error: String(error), diagram_index: index + 1,
        });
        return null;
      }
    };
    try {
      // A font used only inside a diagram may not have loaded at fonts.ready.
      await Promise.all([fontFamily, fontFamilyMono].flatMap(family =>
        ['', 'bold ', 'italic ', 'bold italic '].map(weight =>
          document.fonts.load(`${weight}${fontSize}px ${family}`, source).catch(() => null))));
      let result;
      try {
        result = pele.render(model, {
          idPrefix, fontFamily, fontFamilyMono, fontSize, math,
          maxWidth: layouts[index]?.width || element.clientWidth, autoDirection: false,
          // Preserve Mermaid's previous strict-mode link policy.
          links: false,
        });
      } catch (error) {
        return failure(error, element, source, index);
      }
      element.innerHTML = result.svg;
      const rendered = element.querySelector('svg');
      rendered.classList.add('mermaid-rendered');
      // Standalone SVG exports must retain the resolved document theme too.
      for (const [name, value] of theme) rendered.style.setProperty(name, value);
      rendered.style.setProperty('--pele-font', fontFamily);
      rendered.style.setProperty('--pele-font-mono', fontFamilyMono);
      element.removeAttribute('data-mdtopdf-mermaid');
      element.removeAttribute('data-mdtopdf-source-line');
    } finally {
      probe.remove();
      mathProbe.remove();
    }
  }
  return {warnings, error: null};
}
