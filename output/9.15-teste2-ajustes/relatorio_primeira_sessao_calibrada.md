# Relatório de Análise Eye-Tracking — Primeira Sessão Calibrada

**Sessão:** `9.15-teste2-ajustes`  
**Build:** 0.9.15 (Cocoa Fabric)  
**Data de coleta:** 06/07/2026  
**Participante:** Isabelle  
**Duração:** 6 min 13 s (373 s)  
**Saídas da análise:** `sessoes/output/9.15-teste2-ajustes/`

---

## 1. Contexto e objetivo

Esta sessão é apresentada como a **primeira sessão com captura de olhar calibrada** do pipeline de eye-tracking do Cocoa Fabric. Ela consolida ajustes implementados após sessões piloto (0.9.10–0.9.14), nas quais o olhar era registrado predominantemente como `Wall` e `Checker`, impedindo a análise de tutoriais, máquinas e sacadas de socorro.

**Objetivo da análise:** validar se o sistema passa a registrar de forma confiável:

- fixação em painéis de tutorial (`Paper_*`, `Writebook_*`);
- olhar em máquinas e itens interativos;
- sacadas de socorro (busca por ajuda);
- carga cognitiva via pupila residual (modelo Eckert);
- episódios de confusão/busca visual.

**Referência de comparação:** sessão `9.15-teste` (build 0.9.14), último ciclo completo antes dos ajustes de calibração espacial.

---

## 2. Calibração e mudanças técnicas (build 0.9.15)

| Componente | Ajuste | Efeito esperado |
|---|---|---|
| `EyeTrackingManager` | `composeGazeWithCamera=True` — raio recomposto a partir da **Main Camera** em direção ao ponto de convergência binocular OpenXR | Corrige desvio vertical (eixo Y): esfera de debug e raycast alinhados ao centro visual |
| `GazeTargetDetector` | `tutorialToleranceRadius=0.5 m` (SphereCast dedicado a tutoriais) | Recupera olhares breves nos painéis |
| `InstructionGazeCollider` | `worldPadding=0.20`, `worldDepth=0.60` | Colliders maiores nos painéis de instrução |
| `GazeTarget` + bootstrapper | Captura unificada tutorial / máquina / item | Categorias explícitas no CSV (`TargetCategory`) |
| Pipeline Python | Sacada de socorro = consulta consolidada ao tutorial; análise antes/depois da tarefa | Métricas de prevenção de erros (Heurística #5 Nielsen) |

**Confirmação em runtime** (`diagnostic.txt`):

- `composeGazeWithCamera=True`
- `headReferenceFound=True` → `Main Camera`
- Rastreamento binocular válido em 100% dos frames

---

## 3. Qualidade dos dados

| Indicador | Resultado | Avaliação |
|---|---|---|
| Amostras | 8.275 @ 120 Hz | Completo |
| Rastreamento válido | **100%** | Excelente |
| Lacunas de tracking | **0** | Excelente |
| Piscadas | 60 (0,7%) | Baixo |
| Pupila válida | 100% | Excelente |
| Atividades registradas | 7/7 | Ciclo completo |

A sessão atende critérios mínimos de qualidade para análise quantitativa.

---

## 4. Resultados principais

### 4.1 Distribuição do olhar (captura bruta)

| Categoria | % do tempo | Interpretação |
|---|---:|---|
| **Tutorial** | **45,1%** | Painéis de ajuda dominam o registro — comportamento esperado em ambiente instrucional |
| Máquina | 24,0% | Máquinas finalmente mapeadas |
| Suporte (parede/chão) | 27,4% | Residual aceitável (antes era ~92%) |
| Item | 3,5% | Primeira captura consistente de objetos interativos |

### 4.2 Tempo de fixação por tipo de alvo (dwell)

| Tipo | Tempo (s) | % da sessão |
|---|---:|---:|
| Tutorial | **173,9** | **46,6%** |
| Máquina | 82,3 | 22,1% |
| Suporte | 102,5 | 27,5% |
| Item | 14,3 | 3,8% |

**Painéis mais consultados:**

| Alvo | Tempo (s) | Visitas |
|---|---:|---:|
| `Writebook_5` | 95,3 | 48 |
| `Paper_0` | 57,8 | 23 |
| `Mixer` | 37,4 | 19 |
| `Toaster` | 19,6 | 8 |
| `Bandeja` (item) | 7,1 | 14 |

### 4.3 Fixações em tutorial (algoritmo I-DT)

| Métrica | Valor |
|---|---|
| Nº de fixações | **329** |
| Duração média | **0,42 s** |
| Duração máxima | **2,68 s** |
| Painel com mais fixações | `Writebook_5` (195 fixações, 71 s) |

Indica leitura sustentada dos tutoriais, não apenas glances espúrios.

### 4.4 Sacadas de socorro e consulta ao tutorial

Definição operacional: cada **consulta consolidada** ao tutorial = uma sacada de socorro.

| Métrica | Valor |
|---|---|
| Total de sacadas de socorro | **63** |
| Consultas **antes** do início da tarefa | 5 (9,1 s) — comportamento **antecipatório** |
| Consultas **depois** do início da tarefa | 10 (6,0 s) — comportamento **reativo** |
| Fora da janela de 8 s | 48 — leituras longas, distantes do marco de `Activity` |

**Exemplos interpretáveis:**

- `Paper_0` consultado **antes** de `DescascarSemente` (offset −4,7 s) → leitura antecipatória da instrução.
- `Writebook_6` consultado **depois** de `TorrarAmendoa` (offset +1,7 s) → busca reativa após ligar a máquina.

### 4.5 Carga cognitiva — Modelo Eckert (PLR)

| Parâmetro | Valor |
|---|---|
| Modelo | log |
| Baseline pupilar | 2,81 mm |
| RMSE | 0,48 mm |
| R² | −0,03 |
| Pupila residual média | 0,09 mm |
| Calibração individual | Não (parâmetros padrão) |

O filtro de Eckert está operacional e gera `residual_pupil_timeline.png` e `eckert_plr_fit.png`. R² ainda baixo — calibração por participante é o próximo passo para validação da pupila como indicador de carga.

### 4.6 Confusão e busca visual

| Métrica | Valor |
|---|---|
| Tempo em confusão | 11,8% da sessão |
| Episódios detectados | 6 |
| Coeficiente K médio | **+1,31** (atenção focal/leitura) |
| Entropia estacionária Hs | 4,32 bits |
| Entropia de transição Ht | 2,11 bits |

Episódios concentrados em `Misturar` (2) e `Formar` (4), com varredura entre `Mixer`, `Writebook_5`, `Bandeja` e `Checker` — padrão compatível com busca de orientação durante etapas mais complexas.

---

## 5. Resultados por atividade

| Atividade | Duração (s) | Tutorial % | Sacadas | Confusão % | Pupila residual (mm) |
|---|---:|---:|---:|---:|---:|
| CortarCacau | 72 | 42,9% | 6 | 4,3% | −0,21 |
| SecarSemente | 31 | **66,8%** | 4 | 0,9% | −0,02 |
| DescascarSemente | 30 | 22,6% | 5 | 2,9% | −0,06 |
| TorrarAmendoa | 18 | 57,4% | 3 | 3,8% | −0,02 |
| Moer | 26 | 32,1% | 3 | 4,5% | +0,22 |
| Misturar | 22 | 26,1% | 4 | 18,9% | +0,25 |
| Formar | 175 | 52,4% | **38** | 19,4% | +0,22 |

**Destaques:**

- **SecarSemente** e **TorrarAmendoa**: maior proporção de olhar em tutorial — leitura de instruções antes de operar máquinas.
- **Formar**: etapa mais longa; 38 sacadas de socorro e maior tempo em confusão — etapa de maior demanda cognitiva e consulta ao `Writebook_5`.

---

## 6. Comparação com sessão anterior (validação da calibração)

| Métrica | 9.15-teste (0.9.14) | 9.15-teste2 (0.9.15) | Melhoria |
|---|---:|---:|---|
| Tempo em tutorial | 1,4% | **46,6%** | **+34×** |
| Fixações em tutorial | 13 | **329** | **+25×** |
| Duração média fixação tutorial | 0,22 s | **0,42 s** | **+91%** |
| Sacadas de socorro | 6 | **63** | **+10×** |
| Tempo em máquinas | 5,8 s | **82,3 s** | **+14×** |
| Tempo em itens | 0 s | **14,3 s** | novo |
| Olhar em parede | 37,9% | **2,0%** | resolvido |
| Olhar no chão | 53,7% | **5,0%** | resolvido |
| Confusão (artefato) | 57,4% | **11,8%** | métrica agora válida |

A comparação confirma que os ajustes de calibração espacial (eixo Y) e de captura (colliders + tolerância) transformaram dados antes inutilizáveis em dados analisáveis.

---

## 7. Limitações e ressalvas

1. **Janela de consulta ao tutorial (`window_s=8 s`)**: 48 de 63 consultas classificadas como `fora_janela` — leituras longas de tutorial não se encaixam no marco de início de atividade. Recomenda-se ampliar para 15–20 s nas próximas análises.
2. **Calibração Eckert**: R² ≈ 0 sem CSV de calibração individual; pupila residual deve ser interpretada com cautela até calibração por participante.
3. **Máquinas**: `HitY` médio ≈ 0,19 m sugere captura na base das máquinas, não no painel frontal — pode ser refinado nos colliders.
4. **`task_dwell_s` = 0**: categoria `task` ainda não mapeada; sacadas de socorro não dependem mais disso.
5. **Sessão única**: resultados validam o pipeline, mas generalização exige réplicas com outros participantes.

---

## 8. Conclusão

A sessão `9.15-teste2-ajustes` cumpre os critérios para ser apresentada como a **primeira sessão calibrada** do estudo:

- Captura de olhar alinhada ao centro visual do headset;
- Registro sustentado de tutoriais (46,6% do tempo, fixações até 2,7 s);
- Máquinas e itens interativos mapeados;
- 63 sacadas de socorro detectadas, com consultas antecipatórias e reativas;
- Métricas de confusão e pupila residual operacionais;
- Qualidade de rastreamento excelente (100%, zero lacunas).

> **Síntese para apresentação:** Após calibração espacial do olhar (build 0.9.15), o sistema passou de registrar 95% do tempo em parede/chão para capturar 45% em tutoriais e 24% em máquinas, habilitando pela primeira vez a análise quantitativa de sacadas de socorro, consulta a instruções e carga cognitiva no Cocoa Fabric.

---

## 9. Artefatos para apresentação

| Arquivo | Uso sugerido |
|---|---|
| `residual_pupil_timeline.png` | Visão geral: pupila + tutoriais + socorros |
| `residual_pupil_by_activity.png` | Comparação entre as 7 etapas |
| `eckert_plr_fit.png` | Validação do filtro de luminância (Eckert) |
| `by_activity/*/residual_pupil_timeline.png` | Detalhe por etapa (ex.: `SecarSemente`) |
| `tutorial_consultations.csv` | Tabela de consultas antes/depois |
| `dwell_by_target.csv` | Ranking de alvos fixados |
| `summary_session.csv` | Métricas agregadas da sessão |

---

*Relatório gerado automaticamente pelo pipeline de análise eye-tracking — Cocoa Fabric (Heurística #5 Nielsen).*
