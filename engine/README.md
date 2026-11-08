# Kindlefy Core Engine & Assistente de Formatação e Contexto (Gemma 2 2B)

Motor de conversão espacial de documentos (PDF, TXT, Markdown, DOCX, HTML, EPUB) para livros Kindle (EPUB 3 + MOBI) com:
- **XY-Cut Multi-Column Reflow**: Desfaz layouts de 2 colunas sem misturar linhas horizontalmente.
- **Assistente de Formatação e Contexto (Gemma 2 2B Instruct + GBNF + Invariant Guard)**:
  - **Pass 0**: Limpeza léxica de ligaduras (`ﬁ` -> `fi`), mojibake UTF-8, remoção de cabeçalhos/rodapés repetitivos e números de página.
  - **Pass 1**: Classificação de hierarquia de títulos, capítulos, subtítulos e epígrafes com gramática GBNF estrita.
  - **Pass 2**: Costura de quebras de linha de PDF, viradas de página e desifenização inteligente (`desenvol-\nvimento` vs `guarda-\nchuva`).
  - **Pass 3**: Cirurgião de micro-spans de OCR protegido pelo `InvariantGuard` (bloqueia alucinações e protege siglas como `MP3`, `H2O`).
  - **Pass 4**: Auditoria editorial de paginação, capitulares (*drop caps*), órfãs/viúvas e sumário (TOC).
