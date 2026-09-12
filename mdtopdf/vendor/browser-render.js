async () => {
  const warnings = [];
  const decode = value => new TextDecoder().decode(Uint8Array.from(atob(value), c => c.charCodeAt(0)));
  for (const element of document.querySelectorAll('[data-mdtopdf-math]')) {
    const source = decode(element.dataset.mdtopdfMath);
    const displayMode = element.dataset.display === 'block';
    try {
      katex.render(source, element, {displayMode, throwOnError: true, trust: false, strict: 'ignore', output: 'html'});
    } catch (error) {
      element.textContent = source;
      element.className = displayMode ? 'math-source math-display' : 'math-source';
      warnings.push({type: 'math_fallback', message: 'KaTeX could not render this formula; source is shown.', error: String(error)});
    }
    element.removeAttribute('data-mdtopdf-math');
    element.removeAttribute('data-display');
  }
  const diagrams = document.querySelectorAll('[data-mdtopdf-mermaid]');
  if (diagrams.length) {
    mermaid.initialize({startOnLoad: false, securityLevel: 'strict', flowchart: {htmlLabels: false}});
    let index = 0;
    for (const element of diagrams) {
      const {svg} = await mermaid.render(`mdtopdfDiagram${index++}`, decode(element.dataset.mdtopdfMermaid));
      element.innerHTML = svg;
      element.querySelector('svg').classList.add('mermaid-rendered');
      element.removeAttribute('data-mdtopdf-mermaid');
    }
  }
  return warnings;
}
