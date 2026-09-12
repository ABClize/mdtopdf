

<h1 align="center">mdtopdf: CLI de Markdown a PDF amigable para agentes</h1>

<p align="center">
  <a href="README.md">English</a> | <a href="README_CN.md">中文文档</a> | Español
</p>

<p align="center">
  <a href="#inicio-rápido"><img src="https://img.shields.io/badge/Quick_Start-2_min-blue?style=for-the-badge" alt="Quick Start"></a>
  <a href="#flujo-de-trabajo-para-agentes"><img src="https://img.shields.io/badge/Agent_Friendly-JSON_Output-green?style=for-the-badge" alt="Agent Friendly"></a>
  <a href="#salida-visual"><img src="https://img.shields.io/badge/PDF_Pages-Rendered-purple?style=for-the-badge" alt="Rendered PDF pages"></a>
  <a href="https://pypi.org/project/agent-markdown-pdf/"><img src="https://img.shields.io/pypi/v/agent_markdown_pdf.svg?style=for-the-badge" alt="PyPI version"></a>
  <a href="https://github.com/ABClize/mdtopdf/blob/main/LICENSE"><img src="https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge" alt="License"></a>
</p>

<p align="center">
  <img src="https://img.shields.io/pypi/pyversions/agent_markdown_pdf.svg" alt="Python versions">
  <img src="https://img.shields.io/badge/output-JSON_%2B_Human-blueviolet" alt="JSON and human output">
  <img src="https://img.shields.io/badge/backend-Chromium-2f855a" alt="Chromium backend">
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
- **Archivos locales de entrada, archivos locales de salida** - con un navegador sin interfaz gráfica, sin paso de subida, sin servicio de renderizado remoto.
- **Más que Markdown plano** - se renderizan enlaces de Obsidian, resaltados, frontmatter, comentarios y callouts.

## Inicio rápido

Instale desde PyPI en su entorno de Python:

```shell
python -m pip install "agent-markdown-pdf>=0.3.0"
```

La distribución en PyPI es `agent-markdown-pdf`; instala el comando `mdtopdf`. No utilice `mdtopdf` como nombre del paquete en PyPI; el nombre de la distribución es intencionalmente distinto al del comando.

| Caso de uso | Nombre |
| --- | --- |
| Instalar desde PyPI | `agent-markdown-pdf` |
| Ejecutar la CLI | `mdtopdf` |
| Importar en Python | `mdtopdf` |

Verificar el entorno antes de la primera conversión:

```shell
mdtopdf doctor --render-check --json
```

El paquete instala las dependencias de Python, incluido Playwright. También necesita
un navegador Chromium compatible y las fuentes del documento. Chrome, Edge y Chromium
se detectan automáticamente; consulte [Configuración del navegador](#configuración-del-navegador)
si no se encuentra ninguno.

Convertir un archivo:

```shell
mdtopdf convert report.md -o report.pdf --overwrite
```

Pruebe el documento de prueba visual incluido:

```shell
git clone https://github.com/ABClize/mdtopdf.git
cd mdtopdf
python -m pip install -e ".[dev]"
python -m playwright install chromium --no-shell
mdtopdf html examples/visual-test-en.md -o visual-test-en.html --overwrite
mdtopdf convert examples/visual-test-en.md -o visual-test-en.pdf --overwrite --json
```

La misma prueba visual también está disponible en chino en `examples/visual-test-cn.md`.

## Actualización

No existe el comando `mdtopdf update`. Para una versión instalada con pip,
active el mismo entorno virtual o seleccione el mismo intérprete de Python:

```shell
python -m pip install --upgrade agent-markdown-pdf
python -m mdtopdf --version
```

Esto actualiza desde el índice de paquetes, no desde la rama de desarrollo.
Si instaló con pipx o uv tool, use el mecanismo de actualización de esa herramienta.
Para instalaciones editables o desde código fuente, actualice la rama correspondiente
y reinstale desde ese directorio, sin sustituirla accidentalmente por la versión de PyPI.

Fije una versión probada en las dependencias del despliegue; no actualice en cada tarea.
Después de actualizar a 0.3.0 o posterior, ejecute `mdtopdf doctor --render-check --json`
y revise un PDF representativo. Si Playwright necesita otro navegador administrado,
consulte [Configuración del navegador](#configuración-del-navegador).
La conversión no busca actualizaciones ni actualiza el paquete o navegador automáticamente.

## Flujo de trabajo para agentes

La habilidad de agente incluida se encuentra en [`mdtopdf/skills/SKILL.md`](https://github.com/ABClize/mdtopdf/blob/main/mdtopdf/skills/SKILL.md). Utilice ese archivo cuando otro agente necesite una guía de ejecución compacta para `mdtopdf`.

```shell
mdtopdf doctor --json
mdtopdf convert report.md -o report.pdf --overwrite --json
```

Los agentes pueden enviar Markdown UTF-8 sin crear un archivo de entrada:

```shell
printf '# Report\n\nGenerated by an agent.\n' | mdtopdf convert - -o report.pdf --json
```

En PowerShell, configure la codificación de la tubería:

```powershell
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)
'# Informe' | mdtopdf convert - -o report.pdf --json
```

`convert -` requiere un archivo de salida. Los recursos relativos se buscan desde
el directorio de trabajo o `--base-url`; `--resource-dir` resuelve adjuntos sin ruta.
`--title` cambia el título y encabezado predeterminados (`stdin`).
JSON indica `input: "-"` y `source: "stdin"`. La entrada vacía o no UTF-8 produce un error.
`html` sigue usando archivos.

Una conversión exitosa puede incluir advertencias. Revise `warnings` o use `--strict`
para rechazarlas sin reemplazar la salida existente. También se admite en `html`.
`doctor --render-check --json` prueba PDF, KaTeX y Mermaid; no garantiza el mismo
aspecto con fuentes distintas. Códigos de salida: 0 éxito, 1 fallo de ejecución o
verificación estricta, 2 argumentos inválidos.

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
Markdown -> markdown-it-py HTML -> theme/custom CSS -> Chromium PDF
```

Una sesión de Chromium renderiza KaTeX y Mermaid incluidos, espera las fuentes
e imágenes y genera el PDF. No necesita WeasyPrint, MSYS2, Mermaid CLI ni una
instalación separada de Node.js. No se descarga ningún navegador durante la conversión.

### Actualización desde 0.2.x

Los comandos y la API de Python se conservan, pero el motor cambia a Chromium,
sin alternativa WeasyPrint. Verifique el navegador y un documento representativo
antes de actualizar tareas automáticas. La paginación, las fuentes y el CSS de
impresión personalizado pueden cambiar. No fije el valor del motor antiguo al
procesar JSON. Consulte [CHANGELOG.md](CHANGELOG.md).

## Características

| Característica | Notas |
| --- | --- |
| Salida JSON | `--json` está disponible para conversión, vista previa HTML, doctor y listado de temas. |
| Verificaciones del entorno | `doctor --json` verifica importaciones de Python, el navegador, los recursos KaTeX/Mermaid incluidos y las fuentes recomendadas. |
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
- Diagramas Mermaid con los recursos incluidos, renderizados en Chromium

El HTML crudo está deshabilitado por defecto, excepto por el subconjunto seguro anterior. Para Markdown local de confianza, pase `--unsafe-html`.

## Configuración del navegador

PDF requiere Chromium. HTML también lo necesita si contiene fórmulas o Mermaid;
el HTML sin estos elementos se exporta sin iniciar un navegador y no verifica
la carga de imágenes.

Orden de selección: `MDTOPDF_BROWSER_EXECUTABLE`, `PUPPETEER_EXECUTABLE_PATH`,
Chromium de Playwright instalado, y Chrome/Edge/Chromium del sistema.
Una ruta explícita inválida es un error, no provoca un cambio silencioso de navegador.

Si no hay un navegador disponible:

```shell
python -m playwright install chromium --no-shell
mdtopdf doctor --render-check --json
```

`doctor --json` muestra la ruta y `tools.browser.source`. `--render-check` verifica
que el navegador realmente se inicia. Para seleccionar uno explícitamente:

```powershell
$env:MDTOPDF_BROWSER_EXECUTABLE = "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
mdtopdf doctor --render-check --json
```

```shell
export MDTOPDF_BROWSER_EXECUTABLE="$(command -v google-chrome)"
mdtopdf doctor --render-check --json
```

Se utiliza una sesión nueva, nunca su perfil personal. Los errores de navegador
incluyen `error_code`, el mensaje original y una sugerencia `hint`.

## Notas de la plataforma

Use Python 3.10+ y un navegador Chromium reciente. Playwright incluye su controlador;
no necesita instalar Node.js o npm por separado. Windows y macOS ya no requieren
MSYS2 ni Pango de Homebrew.

En Debian/Ubuntu compatible, prepare las bibliotecas del navegador y las fuentes:

```shell
python -m playwright install-deps chromium
sudo apt-get update
sudo apt-get install -y --no-install-recommends \
  fontconfig fonts-liberation fonts-dejavu-core fonts-noto-cjk fonts-stix
fc-cache -f
```

Ejecute como usuario **no root**, con soporte para el sandbox del navegador.
Si AppArmor bloquea Chromium descargado, configure un Chrome del sistema permitido
por la política del equipo. No desactive el sandbox para evitar este error.

El tema coloca las fuentes latinas antes de CJK. Linux usa Liberation Sans /
DejaVu Sans para texto latino y números, Noto Sans CJK SC para chino y Cascadia
Mono / Cascadia Code si están disponibles; en caso contrario usa fuentes
monoespaciadas del sistema. Debian ofrece `fonts-cascadia-code`.

Windows mantiene su pila de fuentes del sistema. Microsoft YaHei y Segoe UI Emoji
no son requisitos de Linux y nunca se descargan ni se incluyen en el paquete.
Los emojis usan fuentes instaladas; Linux prioriza Noto Emoji monocromo y utiliza
Noto Color Emoji como alternativa. Revise PDFs representativos: cambiar de motor
no hace idénticas las fuentes o secuencias emoji entre sistemas operativos.
KaTeX incluye sus fuentes matemáticas; STIX es un respaldo opcional.

El CSS personalizado puede definir fuentes con `@font-face`. La comprobación
estática verifica archivos locales; las fuentes remotas quedan sin verificar.
Las advertencias no sustituyen la revisión del PDF. Use `--strict` para rechazarlas.

Las imágenes, el CSS y las fuentes pueden acceder a archivos locales o URL remotas.
La conversión bloquea JavaScript del documento incluso con `--unsafe-html`, pero
no aísla la red ni el sistema de archivos. Restrinja estos permisos para documentos
no confiables. HTML exportado con `--unsafe-html` sigue siendo contenido de confianza
al abrirlo fuera de la conversión.

## Desarrollo

```shell
git clone https://github.com/ABClize/mdtopdf.git
cd mdtopdf
python -m pip install -e ".[dev]"
python -m playwright install chromium --no-shell
python -m pytest tests/ -q
```

Compilar y verificar el paquete:

```shell
python -m build
python -m twine check dist/*
```

## Licencia

MIT. KaTeX y Mermaid incluyen sus licencias MIT en `mdtopdf/vendor/katex/LICENSE` y `mdtopdf/vendor/mermaid/LICENSE`.

`mdtopdf` no incluye fuentes corporales CJK, fuentes de emojis ni fuentes propietarias del sistema. El tema predeterminado hace referencia a fuentes del sistema local como Segoe UI, Microsoft YaHei, PingFang SC, Segoe UI Emoji, Noto Sans CJK SC, Noto Emoji, Noto Color Emoji, Cascadia Code y Consolas, pero esos archivos de fuente provienen del sistema operativo o entorno de ejecución del usuario. Las imágenes públicas de Linux deberían preferir la línea base de fuentes abiertas mencionada anteriormente.
