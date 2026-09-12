

<h1 align="center">mdtopdf: CLI de Markdown a PDF amigable para agentes</h1>

<p align="center">
  <a href="https://github.com/ABClize/mdtopdf/blob/main/README_CN.md">中文文档</a>
</p>

<p align="center">
  <a href="#quick-start"><img src="https://img.shields.io/badge/Quick_Start-2_min-blue?style=for-the-badge" alt="Quick Start"></a>
  <a href="#agent-workflow"><img src="https://img.shields.io/badge/Agent_Friendly-JSON_Output-green?style=for-the-badge" alt="Agent Friendly"></a>
  <a href="#visual-output"><img src="https://img.shields.io/badge/PDF_Pages-Rendered-purple?style=for-the-badge" alt="Rendered PDF pages"></a>
  <a href="https://pypi.org/project/agent-markdown-pdf/"><img src="https://img.shields.io/pypi/v/agent_markdown_pdf.svg?style=for-the-badge" alt="PyPI version"></a>
  <a href="https://github.com/ABClize/mdtopdf/blob/main/LICENSE"><img src="https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge" alt="License"></a>
</p>

<p align="center">
  <img src="https://img.shields.io/pypi/pyversions/agent_markdown_pdf.svg" alt="Python versions">
  <img src="https://img.shields.io/badge/output-JSON_%2B_Human-blueviolet" alt="JSON and human output">
  <img src="https://img.shields.io/badge/backend-WeasyPrint-2f855a" alt="WeasyPrint backend">
  <img src="https://img.shields.io/badge/status-alpha-f59e0b" alt="Alpha status">
</p>

**Un solo comando** proporciona a los agentes una ruta controlada de Markdown a PDF.

<p align="center">
  <img src="https://raw.githubusercontent.com/ABClize/mdtopdf/main/assets/readme/cover.png" alt="mdtopdf cover" width="900">
</p>

---

## Por qué funciona para agentes

Los agentes son buenos escribiendo Markdown. El problema es la transferencia: los PDF exportados a través de rutas ad hoc rara vez comparten el mismo estilo. `mdtopdf` proporciona al usuario una interfaz de línea de comandos donde el estilo puede definirse de antemano.

- **Amigable para agentes** - `mdtopdf --help` es una descripción de interfaz que un agente puede leer.
- **JSON cuando importa** - la conversión, la vista previa HTML, las verificaciones del entorno y el listado de temas pueden devolver salidas legibles por máquina.
- **Archivos locales de entrada, archivos locales de salida** - sin dependencia de navegador, sin paso de subida, sin servicio de renderizado remoto.
- **Más que Markdown plano** - se renderizan enlaces de Obsidian, resaltados, frontmatter, comentarios y callouts.

## Inicio rápido

Instalación desde PyPI:

```shell
python -m pip install agent-markdown-pdf
```

La distribución en PyPI es `agent-markdown-pdf`; instala el comando `mdtopdf`. No utilice `mdtopdf` como nombre del paquete en PyPI; el nombre de la distribución es intencionalmente distinto al del comando.

| Caso de uso | Nombre |
| --- | --- |
| Instalar desde PyPI | `agent-markdown-pdf` |
| Ejecutar la CLI | `mdtopdf` |
| Importar en Python | `mdtopdf` |

Verificar la máquina:

```shell
mdtopdf doctor --json
```

Convertir un archivo:

```shell
mdtopdf convert report.md -o report.pdf --overwrite
```

Pruebe el documento de prueba visual incluido:

```shell
git clone https://github.com/ABClize/mdtopdf.git
cd mdtopdf
python -m pip install -e .[dev]
mdtopdf html examples/visual-test-en.md -o visual-test-en.html --overwrite
mdtopdf convert examples/visual-test-en.md -o visual-test-en.pdf --overwrite --json
```

La misma prueba visual también está disponible en chino en `examples/visual-test-cn.md`.

## Flujo de trabajo para agentes

La habilidad de agente incluida se encuentra en [`mdtopdf/skills/SKILL.md`](https://github.com/ABClize/mdtopdf/blob/main/mdtopdf/skills/SKILL.md). Utilice ese archivo cuando otro agente necesite una guía de ejecución compacta para `mdtopdf`.

```shell
mdtopdf doctor --json
mdtopdf convert report.md -o report.pdf --overwrite --json
```

Utilice la vista previa HTML cuando el diseño necesite una revisión rápida:

```shell
mdtopdf html report.md -o report.html --overwrite --json
mdtopdf convert report.md -o report.pdf --overwrite --json
```

`convert --json` devuelve la ruta de entrada, ruta de salida, tamaño del archivo, tema, resumen de verificación de fuentes, advertencias y método de renderizado. Si la conversión falla en modo JSON, el error está lo suficientemente estructurado para que un agente pueda mostrar el comando, explicar la causa probable y reintentarlo después de aplicar una corrección.

## Salida visual

La galería a continuación se renderiza desde el PDF final producido por `examples/visual-test-en.md`. Muestra las páginas reales que un agente puede entregar a un usuario: encabezados, callouts, tablas, código, matemáticas, imágenes, Mermaid y paginación.

| Página 1 | Página 2 |
| --- | --- |
| <img src="https://raw.githubusercontent.com/ABClize/mdtopdf/main/assets/readme/pdf-page-en-1.png" alt="PDF page 1" width="420"> | <img src="https://raw.githubusercontent.com/ABClize/mdtopdf/main/assets/readme/pdf-page-en-2.png" alt="PDF page 2" width="420"> |
| Página 3 | Página 4 |
| <img src="https://raw.githubusercontent.com/ABClize/mdtopdf/main/assets/readme/pdf-page-en-3.png" alt="PDF page 3" width="420"> | <img src="https://raw.githubusercontent.com/ABClize/mdtopdf/main/assets/readme/pdf-page-en-4.png" alt="PDF page 4" width="420"> |
| Página 5 | Página 6 |
| <img src="https://raw.githubusercontent.com/ABClize/mdtopdf/main/assets/readme/pdf-page-en-5.png" alt="PDF page 5" width="420"> | <img src="https://raw.githubusercontent.com/ABClize/mdtopdf/main/assets/readme/pdf-page-en-6.png" alt="PDF page 6" width="420"> |

## Cómo funciona

```text
Markdown -> markdown-it-py HTML -> theme/custom CSS -> WeasyPrint PDF
```

El renderizado de Mermaid es opcional. Si existe un comando local `mmdc`, los bloques Mermaid se renderizan como SVG. Si falta, la conversión sigue siendo exitosa y los bloques Mermaid permanecen visibles como código resaltado.

## Características

| Característica | Notas |
| --- | --- |
| Salida JSON | `--json` está disponible para conversión, vista previa HTML, doctor y listado de temas. |
| Verificaciones del entorno | `doctor --json` verifica importaciones de Python, bibliotecas nativas de WeasyPrint, rutas de DLL de Windows, disponibilidad de Mermaid y fuentes recomendadas. |
| Renderizado local | Markdown, CSS, matemáticas, generación de SVG de Mermaid y exportación de PDF se mantienen en la máquina. |
| Vista previa HTML | Genere HTML independiente antes de la exportación a PDF para una inspección visual rápida. |
| Compatibilidad con Obsidian | Wikilinks, alias, ocultamiento de frontmatter, comentarios, resaltados y callouts con tipo. |
| Markdown documental | Tablas, listas de tareas, notas al pie, anclajes de encabezados, código con valla y resaltado con Pygments. |
| Matemáticas KaTeX | Renderizado de TeX en línea y en bloques con activos KaTeX incluidos, sin usar un CDN. |
| HTML seguro por defecto | Se permiten etiquetas comunes de documento en línea; el HTML crudo inseguro permanece escapado a menos que se active explícitamente. |
| API de Python | Convierta cadenas o archivos Markdown desde su propio código. |

## Comandos

Renderizar un PDF:

```shell
mdtopdf convert report.md -o report.pdf
mdtopdf convert report.md -o report.pdf --overwrite
```

Vista previa HTML:

```shell
mdtopdf html report.md -o report.html --overwrite
```

Establecer metadatos del documento y elementos de página:

```shell
mdtopdf convert report.md -o report.pdf --title "Report"
mdtopdf convert report.md -o report.pdf --header "Report" --footer "Draft"
mdtopdf convert report.md -o report.pdf --no-header --no-footer
```

Usar CSS adicional o rutas de búsqueda de recursos:

```shell
mdtopdf convert report.md -o report.pdf --css print.css
mdtopdf convert report.md -o report.pdf --base-url assets
mdtopdf convert report.md -o report.pdf --resource-dir attachments
```

El CSS personalizado es el punto de extensión de estilo. Coloque las reglas específicas del documento en un archivo CSS; las fuentes, espaciado, colores, reglas de página y estilo de bloques de código se definen allí. Use directamente una fuente instalada en el sistema, o defina `@font-face` para un archivo de fuente local. Las URL relativas en CSS se resuelven desde la URL base del archivo Markdown, por lo que use `--base-url` cuando esos activos se encuentren junto a su documento:

```css
@font-face {
  font-family: "Report Sans";
  src: url("fonts/NotoSansSC-Regular.otf");
}

:root {
  font-family: "Report Sans", "Noto Sans SC", "Source Han Sans SC", sans-serif;
}

code,
pre {
  font-family: "Cascadia Code", "Liberation Mono", monospace;
}
```

Luego, pase el archivo CSS:

```shell
mdtopdf convert report.md -o report.pdf --css print.css --base-url .
```

Durante la exportación, `mdtopdf` verifica las pilas de fuentes CSS finales. Las fuentes faltantes no detienen la generación del PDF, pero se reportan en las advertencias de la CLI y en el campo `warnings` del JSON.

Devolver JSON:

```shell
mdtopdf --json convert report.md -o report.pdf --overwrite
mdtopdf doctor --json
mdtopdf themes list --json
```

Permitir HTML crudo solo para Markdown local de confianza:

```shell
mdtopdf convert trusted.md -o trusted.pdf --unsafe-html
```

## API de Python

```python
from mdtopdf import (
    markdown_file_to_html,
    markdown_file_to_pdf,
    markdown_to_html,
    markdown_to_pdf,
)

rendered = markdown_to_html("# Report\n\n==highlight==")
print(rendered.html)

markdown_to_pdf("# Report\n\nBody", "report.pdf", title="Report", overwrite=True)
markdown_file_to_html("report.md", output_path="report.html", overwrite=True)
markdown_file_to_pdf("report.md", output_path="report.pdf", overwrite=True)
```

## Compatibilidad con Markdown

`mdtopdf` admite:

- CommonMark
- Tablas
- Tachado
- Listas de tareas
- Notas al pie
- Anclajes de encabezados
- Bloques de código con valla y resaltado con Pygments
- Marcas de resaltado estilo Obsidian `==highlight==`
- Wikilinks estilo Obsidian `[[target|alias]]`
- Comentarios estilo Obsidian `%%comment%%` fuera del código
- Ocultamiento de frontmatter Obsidian/YAML al inicio del archivo
- Callouts estilo Obsidian como `> [!note] Título`
- Etiquetas HTML en línea seguras como `<br>`, `<kbd>`, `<mark>`, `<sup>` y `<sub>`
- Matemáticas TeX a través de `$inline$`, `$$block$$` y entornos `amsmath` comunes
- Diagramas Mermaid a través de `mmdc` local, cuando esté instalado

El HTML crudo está deshabilitado por defecto, excepto por el subconjunto seguro anterior. Para Markdown local de confianza, pase `--unsafe-html`.

## Diagramas Mermaid

Instalar un renderizador local persistente:

```shell
npm install -g @mermaid-js/mermaid-cli
```

`mdtopdf` no llama a Mermaid.ink y no descarga Mermaid CLI a través de `npx` durante la conversión. Ejecute `mdtopdf doctor --json` para verificar si el renderizado de Mermaid está disponible.

## Notas de la plataforma

`mdtopdf` requiere Python 3.10+ e instala sus dependencias de Python desde PyPI: `click`, `markdown-it-py`, `mdit-py-plugins`, `pygments`, `latex2mathml`, `matplotlib`, `mini-racer` y `weasyprint`.

WeasyPrint también necesita bibliotecas nativas como Pango, GLib y Cairo. Los administradores de paquetes de Linux y macOS generalmente las proporcionan a través de paquetes del sistema.

El tema predeterminado usa una pila de fuentes latina primero, segura para PDFium. Las fuentes latinas se listan antes que las fuentes CJK para que los dígitos ASCII, fechas, versiones y números de página no se incrusten en subconjuntos de fuentes CJK que algunos renderizadores Chrome/PDFium manejan mal. El texto en chino aún hace referencia a la parte CJK de la pila.

Para contenedores Linux o entornos aislados (sandboxes) de agentes, use fuentes abiertas que puedan instalarse desde el administrador de paquetes de la distribución. La línea base recomendada es:

```shell
sudo apt-get install -y --no-install-recommends \
  fontconfig \
  fonts-liberation \
  fonts-dejavu-core \
  fonts-noto-cjk \
  fonts-stix
fc-cache -f
```

Con esa configuración, la salida en Linux usa `Liberation Sans` / `DejaVu Sans` para texto y dígitos latinos, `Noto Sans CJK SC` para chino y STIX como respaldo para matemáticas. Microsoft YaHei y Segoe UI Emoji no son requisitos de ejecución en Linux y no se instalan ni distribuyen con `mdtopdf`.

Los bloques de código prefieren `Cascadia Mono` / `Cascadia Code`, luego `Consolas`, `Noto Sans Mono CJK SC`, `Liberation Mono` y `DejaVu Sans Mono`. En Debian, `fonts-cascadia-code` proporciona las fuentes Cascadia; en otras imágenes Linux, proporcione Cascadia Code usted mismo o permita que el tema use las fuentes monoespaciadas instaladas como respaldo.

Los emojis se renderizan a través de la fuente de emojis del sistema. En Linux, prefiera el `Noto Emoji` en monocromo para un diseño de PDF estable. `Noto Color Emoji` es más fácil de instalar desde muchos administradores de paquetes de distribuciones y es seguro usarlo como respaldo, pero los emojis a color a menudo se renderizan demasiado pequeños o desalineados en la salida de WeasyPrint/Pango/Cairo/PDFium.

En Windows, instale las bibliotecas nativas por separado. Una configuración común con MSYS2 es:

```powershell
winget install MSYS2.MSYS2
```

Luego, instale Pango desde una shell MSYS2 MINGW64:

```shell
pacman -S mingw-w64-x86_64-pango
```

Finalmente, apunte WeasyPrint al directorio de DLL desde PowerShell. Ajuste la ruta si MSYS2 está instalado en otro lugar:

```powershell
setx WEASYPRINT_DLL_DIRECTORIES "C:\msys64\mingw64\bin"
```

Ejecute esto después de la instalación. La salida JSON también informa si las fuentes recomendadas latinas, CJK, de emojis, monoespaciadas y de respaldo para matemáticas están presentes:

```shell
mdtopdf doctor --json
```

## Desarrollo

```shell
git clone https://github.com/ABClize/mdtopdf.git
cd mdtopdf
python -m pip install -e .[dev]
python -m pytest tests/ -q
```

Compilar y verificar el paquete:

```shell
python -m build
python -m twine check dist/*
```

## Licencia

MIT. Los activos KaTeX incluidos también se distribuyen bajo la licencia MIT; consulte `mdtopdf/vendor/katex/LICENSE`.

`mdtopdf` no incluye fuentes corporales CJK, fuentes de emojis ni fuentes propietarias del sistema. El tema predeterminado hace referencia a fuentes del sistema local como Segoe UI, Microsoft YaHei, PingFang SC, Segoe UI Emoji, Noto Sans CJK SC, Noto Emoji, Noto Color Emoji, Cascadia Code y Consolas, pero esos archivos de fuente provienen del sistema operativo o entorno de ejecución del usuario. Las imágenes públicas de Linux deberían preferir la línea base de fuentes abiertas mencionada anteriormente.
