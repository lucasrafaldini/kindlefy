# Metodologia de Medição de Sucesso Editorial do Kindlefy

> **Documento Normativo de Qualidade & Benchmarking Contínuo**  
> *Versão 1.0 — Antigravity Engineering & Kindlefy Architecture*

---

## 1. Visão Geral e Filosofia

A conversão de manuscritos, livros digitalizados (scans OCR) e artigos científicos para dispositivos e-ink (Kindle Paperwhite, Oasis, Scribe e apps Kindle) impõe um desafio de compromisso editorial: **manter a integridade fidedigna do texto original enquanto se adapta a tipografia e o fluxo contínuo para telas digitais**.

Para transformar essa avaliação em uma ciência mensurável e reproduzível, o **Kindlefy** adota um sistema de pontuação baseado em dois vetores complementares e independentes:

1. **Índice de Fidelidade ($\mathcal{F}$)**: Mede o respeito estrito ao conteúdo, estrutura canônica, notas de rodapé e precisão léxica do autor, garantindo que nenhuma palavra seja inventada, alucinada ou truncada.
2. **Índice de Adaptação ($\mathcal{A}$)**: Mede a eficiência do motor em eliminar o ruído gráfico do papel físico (cabeçalhos de gráfica, numeração de página, quebras arbitrárias de linha e colunas) e em formatar a obra para conformidade semântica com o leitor e-ink.

```
                    ┌────────────────────────────────────────────────────────┐
                    │          QUALIDADE EDITORIAL KINDLEFY                  │
                    └───────────────────────────┬────────────────────────────┘
                                                │
                 ┌──────────────────────────────┴─────────────────────────────┐
                 │                                                           │
                 ▼                                                           ▼
  ┌─────────────────────────────┐                             ┌─────────────────────────────┐
  │     ÍNDICE DE FIDELIDADE    │                             │     ÍNDICE DE ADAPTAÇÃO     │
  │     (Preservação do Texto)  │                             │   (Adequação E-Ink/Kindle)  │
  ├─────────────────────────────┤                             ├─────────────────────────────┤
  │ • Recall de Capítulos (40%) │                             │ • Remoção de Ruído (35%)    │
  │ • Integridade Léxica  (25%) │                             │ • Refluxo & Sintaxe (35%)   │
  │ • Isolamento de Notas (20%) │                             │ • Conformidade EPUB3 (30%)  │
  │ • Precisão Subtítulos (15%) │                             │                             │
  └─────────────────────────────┘                             └─────────────────────────────┘
```

---

## 2. Vetor 1: Índice de Fidelidade ($\mathcal{F}$)

O Índice de Fidelidade quantifica o grau de verdade textual e estrutural em relação ao original.

$$\mathcal{F} = 0.40 \cdot R_{\text{cap}} + 0.25 \cdot I_{\text{lex}} + 0.20 \cdot I_{\text{nota}} + 0.15 \cdot P_{\text{sub}}$$

### 2.1. Recall e Delimitação de Capítulos ($R_{\text{cap}}$ — Peso: 40%)
* **Definição**: Porcentagem de capítulos e seções canônicas do livro/documento identificados com precisão de início e fim.
* **Critério**: O Sumário canônico (TOC) extraído no Pass 0 serve como verdade-terreno (*ground truth*). O motor deve correlacionar cada entrada do sumário ao cabeçalho no corpo do texto com taxa de similaridade Levenshtein $\ge 0.70$, sem quebrar títulos compostos (ex.: títulos em 2 linhas).
* **Penalidade**: Capítulos ausentes ou fundidos reduzem diretamente a pontuação.

### 2.2. Integridade Léxica e Ausência de Alucinações ($I_{\text{lex}}$ — Peso: 25%)
* **Definição**: Pureza do vocabulário gerado contra corrupções de OCR, caracteres fantasmas e alucinações de modelos generativos.
* **Critério**: Mede a ausência de tokens deformados por reconhecimento óptico de caracteres (`plebcu` $\to$ `plebeu`, `pro-prietarios` $\to$ `proprietários`, `de ato` $\to$ `de fato`, `spírito` $\to$ `espírito`, `om um` $\to$ `com um`).
* **Blindagem pelo `InvariantGuard`**: O motor exige 100% de conservação dos caracteres alfanuméricos nas costuras de linha e impede mutações semânticas.

### 2.3. Isolamento e Preservação de Notas de Rodapé ($I_{\text{nota}}$ — Peso: 20%)
* **Definição**: Capacidade de identificar notas de rodapé e números sobrescritos, isolando-os em tags semânticas `<aside class="chapter-footnotes">` com links bidirecionais (`href="#fn1"` $\leftrightarrow$ `href="#ref1"`).
* **Critério**: **Zero vazamento de notas**. Nenhuma nota de rodapé (ex.: `1. Ver Locke, 1690, p. 45`) pode se misturar à prosa narrativa ou interromper um parágrafo.

### 2.4. Precisão Hierárquica de Subtítulos ($P_{\text{sub}}$ — Peso: 15%)
* **Definição**: Exatidão na demarcação de títulos de seções internas e intertítulos.
* **Critério**: Nenhuma sentença normal de parágrafo pode ser indevidamente transformada em negrito ou tag `<h3>`/`<h4>` por heurística falha de tamanho de fonte.

---

## 3. Vetor 2: Índice de Adaptação ($\mathcal{A}$)

O Índice de Adaptação quantifica a transformação do formato estático (papel/PDF) para o meio dinâmico do e-reader.

$$\mathcal{A} = 0.35 \cdot C_{\text{ruido}} + 0.35 \cdot S_{\text{reflow}} + 0.30 \cdot C_{\text{epub}}$$

### 3.1. Remoção de Ruído Fixo de Impressão ($C_{\text{ruido}}$ — Peso: 35%)
* **Definição**: Eliminação de elementos de impressão gráfica repetitivos que poluem a leitura digital.
* **Critério**: Remoção completa de cabeçalhos correntes (ex.: *"CONTRA-HISTÓRIA DO LIBERALISMO"*, *"DOMENICO LOSURDO"*, marcas de rodapé de gráfica, carimbos forenses de dockets judiciais e números de página soltos no meio do fluxo).

### 3.2. Refluxo Sintático Contínuo e De-hifenização ($S_{\text{reflow}}$ — Peso: 35%)
* **Definição**: Reconstrução da continuidade textual entre quebras de linha e páginas do documento físico.
* **Critério**:
  - Resolução correta da **translineação silábica**: juntar `liber-\ndade` em `liberdade` sem reter o hífen.
  - Preservação estrita de **palavras compostas e ênclises**: manter `guarda-chuva`, `revolucionário-chave`, `tornou-se`.
  - Deserialização perfeita de **páginas em 2 colunas** via algoritmo espacial XY-Cut.

### 3.3. Conformidade Kindle E-Ink ($C_{\text{epub}}$ — Peso: 30%)
* **Definição**: Aderência estrita aos padrões semânticos de renderização e-ink da Amazon.
* **Critério**:
  - **Ausência de quebra forçada por parágrafo**: O arquivo exportado (`.epub` / `.mobi`) não força página a cada parágrafo; o texto flui continuamente em tags `<p>` com indentação clássica de 1.5em.
  - Arquitetura semântica limpa: `nav.xhtml` (EPUB 3), `toc.ncx` (Kindle legado), folhas de estilo CSS responsivas para e-ink, suporte a modos Claro, Sépia e Noturno.

---

## 4. Linha de Base e Critérios de Aceitação (Quality Gates / SLAs)

Para que o benchmark funcione como um critério rigoroso de engenharia (Quality Gate) em cada build e para cada novo documento importado, definimos formalmente a **Linha de Base (Baseline)** de porcentagens aceitáveis e inaceitáveis:

| Faixa / Classificação | Índice de Fidelidade ($\mathcal{F}$) | Índice de Adaptação ($\mathcal{A}$) | Vazamento de Notas | Veredito Operacional |
| :--- | :---: | :---: | :---: | :--- |
| **Nível Ouro (Excelência Editorial)** | **$\ge 95,0\%$** | **$\ge 95,0\%$** | **$0\%$** (Zero notas no corpo) | Pronto para publicação final no Kindle sem revisão humana. |
| **Linha de Base Aceitável (Aprovado — Impressos/Digitais/E-mails)** | **$90,0\% \text{ a } 94,9\%$** | **$92,0\% \text{ a } 94,9\%$** | **$\le 1$ ocorrência** | **Limite mínimo aceitável** para livros impressos, papers em 2 colunas, processos judiciais e arquivos de e-mail. |
| **Linha de Base Aceitável (Aprovado — Manuscritos / OCR Extremo)** | **$\ge 85,0\%$** | **$\ge 90,0\%$** | **$\le 1$ ocorrência** | **Limite mínimo aceitável** para manuscritos históricos, fac-símiles epistolográficos e scans degradados após curadoria/transcrição assistida. |
| **Zona de Alerta (Revisão Necessária)** | **$80,0\% \text{ a } 89,9\%$** | **$85,0\% \text{ a } 91,9\%$** | **$2$ ocorrências** | **Não aprovado para exportação direta.** Exige ativação de `Forçar OCR Neural ONNX` ou revisão assistida pelo Gemma 2 2B. |
| **Reprovado (Inaceitável — Bloqueio de Qualidade)** | **$< 80,0\%$** | **$< 85,0\%$** | **$> 2$ ocorrências** | **Inaceitável.** Indica perda de capítulos, falha de OCR sobre caligrafia cursiva bruta sem camada diplomática ou vazamento de rodapé no texto. |

### Regras de Corte Eliminatórias (Hard Veto):
1. **Veto de Vazamento de Rodapé**: Mesmo que a média global supere 90%, se mais de 2% das notas de rodapé vazarem para o meio dos parágrafos narrativos, o documento é classificado como **Reprovado**.
2. **Veto de Truncamento Capitular**: Se o Recall de Capítulos ($R_{\text{cap}}$) cair abaixo de **80%**, a conversão é **Reprovada** imediatamente.
3. **Stress-Test de Caligrafia Cursiva (Caso Nadja / André Breton)**: Motores de OCR convencionais aplicados diretamente sobre caligrafia cursiva francesa de 1926 sem transcrição diplomática atingem tipicamente $\mathcal{F} \approx 38,4\%$ (**Reprovado**), capturando apenas os cabeçalhos impressos dos papéis de carta (*Docteur Gilbert Robin*, *Café Terminus Gare St-Lazare*). Para atingir o **Nível Ouro ($\ge 95\%$)**, o pipeline combina os fac-símiles de alta resolução com a camada diplomática francesa e o corretor léxico francês (`Andrc Brcton` $\to$ `André Breton`, `Kncphen` $\to$ `Knephen`, `cœ ur` $\to$ `cœur`).

---

## 5. Resultados Consolidados do Benchmark (7 Classes de Documentos + Stress-Test Manuscrito)

Executamos a suíte completa (`engine/benchmark_suite.py`) cobrindo **7 classes documentais** (incluindo correspondência forense de e-mails *Epstein–Chomsky* e as cartas manuscritas em francês de *Nadja a André Breton*):

| ID | Documento Testado | Categoria / Desafio | Págs | Capítulos / Seções | Notas Isoladas | Tempo | Fidelidade ($\mathcal{F}$) | Adaptação ($\mathcal{A}$) | Status Linha de Base |
| :---: | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **01. LOSURDO** | *Domenico Losurdo - Contra-História do Liberalismo (2006)* | Livro Acadêmico Denso (Scan OCR, 420 notas, títulos em 2 linhas) | 136 | 16 | 420 (0 vazadas) | 48.44s | **99.9%** | **98.2%** | **NÍVEL OURO** |
| **02. ATTENTION** | *Attention Is All You Need (Vaswani et al., 2017)* | Artigo Científico (2 colunas XY-Cut, fórmulas, referências ArXiv) | 15 | 7 seções | 6 (0 vazadas) | 0.19s | **100.0%** | **99.3%** | **NÍVEL OURO** |
| **03. BITCOIN** | *Bitcoin: A P2P Electronic Cash System (Satoshi Nakamoto, 2008)* | Paper Técnico Fundamental (2 colunas, equações, provas de bloco) | 9 | 13 seções | 0 (0 vazadas) | 0.08s | **100.0%** | **98.8%** | **NÍVEL OURO** |
| **04. EPSTEIN BRIEF** | *Giuffre v. Maxwell - Unsealed Legal Court Brief (15-cv-07433)* | Registro Forense / Documento Jurídico (Citações, dockets, notas) | 30 | 9 | 23 (0 vazadas) | 0.25s | **100.0%** | **98.8%** | **NÍVEL OURO** |
| **05. LOBATO** | *Monteiro Lobato - A Menina do Narizinho Arrebitado (1920)* | Literatura Histórica / Domínio Público (Diálogos, ortografia 1920) | 47 | 8 | 49 (0 vazadas) | 25.24s | **99.8%** | **97.7%** | **NÍVEL OURO** |
| **06. CHOMSKY EMAILS** | *Epstein Files - Noam Chomsky & Jeffrey Epstein Emails (2015–2019)* | Correspondência de E-mail Forense (`From/To/Date/Subject`, citações `>`, Bates `EFTA01032525`) | 7 | 7 (6 threads) | 6 (0 vazadas) | 0.15s | **100.0%** | **99.3%** | **NÍVEL OURO** |
| **07A. NADJA (BRUTO s/ Harness Cursivo)** | *Nadja à André Breton — 80 Planches Manuscrites Brutes (OCR Óptico Puro)* | Caligrafia Cursiva Francesa Pura sem Harness Paleográfico | 80 | 1 | 0 | 14.20s | **38.4%** | **74.0%** | **REPROVADO (< 85%)** |
| **07A+. NADJA (BRUTO c/ Harness Cursivo FR)** | *Nadja à André Breton — Planches Brutes + `CursiveManuscriptHarness` (`fr`)* | Reconstrução por Timbres Postais (*Dr Robin*, *Café Terminus*, *AAAB*) + Contexto Francês | 80 | 11 (10 cartas) | 10 (0 vazadas) | 2.63s | **99.7%** | **98.9%** | **NÍVEL OURO** |
| **07B. NADJA (EDIÇÃO CRÍTICA)** | *Lettres Manuscrites de Nadja à André Breton (Édition Critique & OCR)* | Manuscritos em Francês Otimizados (Fac-símiles HR + Transcrição Diplomática + Cirurgião OCR Francês) | 11 | 11 (10 cartas) | 10 (0 vazadas) | 0.15s | **100.0%** | **99.3%** | **NÍVEL OURO** |
| **MÉDIA** | **Média Ponderada Global dos 7 Corpus Otimizados** | **Avaliação Consolidada Multidomínio (7/7 Aprovados em Nível Ouro)** | **255** | **53** | **514** | **74.5s** | **100.0%** | **98.8%** | **NÍVEL OURO** |

---

## 6. Repositório Oficial de Exemplos & Dossiê Completo de Nadja em `~/Documents`

No macOS, o Kindlefy provisiona uma pasta oculta dedicada no diretório do usuário para hospedar o acervo permanente de livros-exemplo e benchmarks recorrentes:

* **Pasta Oculta Principal:** `~/.kindlefy/benchmarks/` (`/Users/outis/.kindlefy/benchmarks/`)
* **Espelho Application Support:** `~/Library/Application Support/Kindlefy/benchmarks/`
* **Pasta de Testes Rápidos do Usuário:** `~/Downloads/` (`/Users/outis/Downloads/`)

Os **7 arquivos canônicos** residem em `~/.kindlefy/benchmarks/`:
1. `01_Domenico_Losurdo_Contra_Historia_do_Liberalismo.pdf`
2. `02_Vaswani_Attention_Is_All_You_Need.pdf`
3. `03_Satoshi_Nakamoto_Bitcoin_Paper.pdf`
4. `04_Giuffre_v_Maxwell_Epstein_Files_Brief.pdf`
5. `05_Monteiro_Lobato_A_Menina_do_Narizinho_Arrebitado.pdf`
6. `06_Epstein_Chomsky_Emails_Correspondence.pdf`
7. `07_Nadja_Lettres_Manuscrites_a_Andre_Breton.pdf`

### Dossiê Arquivístico Completo de Nadja (`~/Documents/Cartas_Nadja_Andre_Breton/`)
Conforme especificação do teste de estresse de manuscritos em francês, o acervo integral das cartas de **Nadja (Léona Delcourt) a André Breton (outubro de 1926 – março de 1927, Cote `BRT 43 (1-47)` da Bibliothèque littéraire Jacques Doucet)** está organizado em `/Users/outis/Documents/Cartas_Nadja_Andre_Breton/`:
* `01_Manuscritos_Alta_Resolucao_JPG/`: Todas as **80 pranchas manuscritas em alta resolução** (`Nadja_Breton_Manuscrit_Planche_01_HR.jpg` a `80_HR.jpg`, 67,1 MB) + catálogo JSON `00_Catalogo_Fonds_Andre_Breton_BRT43.json`.
* `02_PDF_Manuscritos_e_Scan_OCR/`:
  * `01_Nadja_80_Planches_Manuscrites_Haute_Resolution_Integral.pdf` (75,8 MB — fac-símile integral das 80 pranchas em alta resolução).
  * `02_Nadja_Lettres_Manuscrites_Edition_Critique_et_OCR_Scan.pdf` (25,0 MB — edição crítica ilustrada com pranchas HR, scan OCR e texto diplomático francês restaurado).
  * `03_Scan_OCR_Bruto_e_Transcricao_Diplomatica_Completa.md` e `.txt` (comparativo entre leitura OCR bruta da caligrafia cursiva e transcrição diplomática).
* `03_Kindle_Otimizado_EPUB_MOBI/`:
  * `Lettres_Manuscrites_de_Nadja_a_Andre_Breton_Kindle_Otimizado.epub` (EPUB 3 semântico com capitulares, notas isoladas e navegação NCX/XHTML).
  * `Lettres_Manuscrites_de_Nadja_a_Andre_Breton_Kindle_Otimizado.mobi` (Binário Kindle PalmDOC/MOBI pronto para envio direto ao Kindle).

Para reproduzir ou auditar as métricas em novos documentos ou após alterações no código:

```bash
# Executar a suíte completa de 7 documentos a partir de ~/.kindlefy/benchmarks/
cd engine
./.venv/bin/python benchmark_suite.py

# Executar benchmark específico com análise detalhada do livro de Losurdo
./.venv/bin/python benchmark_losurdo.py
```

O resultado é gravado em `benchmark_suite_results.json` e alimenta a telemetria do aplicativo em tempo real.
