"""Backend FastAPI — Protocol: Simulação de Formulações Farmacêuticas"""

import base64
import json
import os
import anthropic

try:
    from dotenv import load_dotenv
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    load_dotenv(dotenv_path=env_path, override=True)
except ImportError:
    pass

try:
    import groq as groq_sdk
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False


def get_provider() -> str:
    """Retorna 'groq' ou 'claude' conforme configurado."""
    return os.environ.get("PROVIDER", "claude").lower()


def groq_client():
    return groq_sdk.Groq(api_key=os.environ.get("GROQ_API_KEY"))


def claude_client():
    return anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

from fastapi import FastAPI, Request, UploadFile, File
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from sse_starlette.sse import EventSourceResponse

app = FastAPI(title="Protocol — Simulação de Formulações Farmacêuticas")
app.mount("/static", StaticFiles(directory="static"), name="static")


FONTES_OFICIAIS = """
Use a ferramenta de busca web para consultar dados atualizados nas seguintes fontes oficiais antes de responder:
- **ANVISA** (anvisa.gov.br): RDC vigentes, listas de substâncias controladas, monografias, registros
- **Farmacopeia Brasileira** (farmacopeia.anvisa.gov.br): monografias de insumos e formas farmacêuticas
- **USP** (usp.org): United States Pharmacopeia — monografias e especificações
- **European Pharmacopoeia** (edqm.eu): Ph.Eur. — monografias europeias
- **FNFB** — Formulário Nacional da Farmacopeia Brasileira
- **PubMed / Cochrane** para literatura peer-reviewed recente
- **Portarias SVS/MS** sobre substâncias controladas

Faça buscas específicas (ex: "ANVISA RDC vitamina D3 regulamentação", "farmacopeia brasileira excipientes cápsula") para obter dados atuais.
Cite sempre a fonte e a data/versão consultada.
"""


def construir_prompt(dados: dict) -> str:
    componentes     = dados["componentes"]
    qtd_unidade     = float(dados.get("qtd_por_unidade") or dados.get("peso_unidade_mg") or 500)
    unidade         = dados.get("unidade_medida", "mg")
    quantidade      = int(dados["quantidade_unidades"])
    total_lote      = quantidade * qtd_unidade
    unid_por_dose   = int(dados.get("unidades_por_dose") or 1)
    doses_por_dia   = int(dados.get("doses_por_dia") or 1)
    dose_diaria     = unid_por_dose * doses_por_dia * qtd_unidade

    comp_texto = "\n".join(
        f"  - {c['nome']} ({c['tipo']}): {c['percentual']}%"
        for c in componentes
    )
    qtd_linhas = "\n".join(
        f"  - {c['nome']}: {(float(c['percentual']) / 100) * total_lote:.4f} {unidade}"
        for c in componentes
    )

    return f"""Você é um especialista em farmácia industrial e regulação farmacêutica brasileira.

{FONTES_OFICIAIS}

Analise a seguinte formulação farmacêutica e forneça um relatório técnico completo em português:

## DADOS DA FORMULAÇÃO

- **Forma farmacêutica:** {dados["forma_farmaceutica"]}
- **Quantidade a produzir:** {quantidade} unidades
- **Quantidade por unidade:** {qtd_unidade} {unidade}
- **Total do lote:** {total_lote:,.4f} {unidade}
- **Posologia:** {unid_por_dose} unidade(s) por dose · {doses_por_dia} dose(s)/dia
- **Dose diária total:** {dose_diaria:,.4f} {unidade}
- **Indicação pretendida:** {dados.get("indicacao") or "não especificada"}

### Componentes da formulação (% p/p ou p/v):
{comp_texto}

### Quantidades absolutas por lote:
{qtd_linhas}

---

## RELATÓRIO SOLICITADO

Forneça análise completa cobrindo TODOS os tópicos abaixo com formatação Markdown clara:

### 1. 🛒 QUANTIDADES DE COMPRA
Para cada componente ativo:
- Quantidade exata a comprar (com margem de 5-10% de perda)
- Tipos de fornecedores no Brasil
- Forma de compra recomendada
- Condições de armazenamento

### 2. 💊 DOSAGEM POR UNIDADE
Para cada princípio ativo:
- Dose máxima recomendada por unidade
- Dose mínima terapêutica eficaz
- Frequência de administração típica (vezes/dia)
- Dose diária máxima (DDD)
- Avaliação da dose calculada (adequada/alta/baixa)

### 3. 👶👴 RESTRIÇÕES POR FAIXA ETÁRIA
Para cada ativo:
- Uso pediátrico (idade mínima, dose/kg)
- Uso geriátrico (ajustes)
- Contraindicações por idade
- Gestantes (categoria risco)
- Lactantes

### 4. ⚗️ VIABILIDADE FARMACOTÉCNICA
- Compatibilidade físico-química entre componentes
- Estabilidade (temperatura, umidade, luz)
- Adequação dos excipientes
- Técnica de fabricação recomendada
- Problemas de processamento esperados
- Biodisponibilidade esperada

### 5. ⚠️ INCOMPATIBILIDADES FARMACOTÉCNICAS
- Incompatibilidades físicas
- Incompatibilidades químicas
- Incompatibilidades farmacológicas
- Soluções e alternativas para cada problema

### 6. 🏛️ REGULAÇÃO ANVISA
- Categoria regulatória do produto
- Necessidade de registro/notificação
- RDC e normativas aplicáveis
- Classificação de venda
- Exigências de BPF/GMP
- Substâncias controladas (portarias SVS/MS)

### 7. 💼 RESTRIÇÕES COMERCIAIS
- Autorização especial de funcionamento
- Restrições de venda online
- Rotulagem obrigatória
- Requisitos de bula
- Restrições de propaganda

### 8. ✅ RECOMENDAÇÕES FINAIS
- Parecer geral de viabilidade
- Principais alertas
- Próximos passos para registro/fabricação

Cite legislações brasileiras vigentes quando aplicável."""


def _salvar_env(chave_var: str, valor: str):
    """Atualiza ou adiciona uma variável no .env e no processo."""
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    linhas, encontrou = [], False
    if os.path.exists(env_path):
        with open(env_path, encoding="utf-8") as f:
            for linha in f:
                if linha.startswith(f"{chave_var}="):
                    linhas.append(f"{chave_var}={valor}\n"); encontrou = True
                else:
                    linhas.append(linha)
    if not encontrou:
        linhas.append(f"{chave_var}={valor}\n")
    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(linhas)
    os.environ[chave_var] = valor


@app.get("/status-provedor")
async def status_provedor():
    p = get_provider()
    groq_ok = bool(os.environ.get("GROQ_API_KEY"))
    claude_ok = bool(os.environ.get("ANTHROPIC_API_KEY"))
    return {"provider": p, "groq_configurado": groq_ok, "claude_configurado": claude_ok}


@app.post("/configurar-chave")
async def configurar_chave(request: Request):
    """Salva chave API (Claude ou Groq) no .env e valida."""
    try:
        dados = await request.json()
        provedor = dados.get("provedor", "claude")
        chave    = dados.get("chave", "").strip()

        if provedor == "groq":
            if not chave:
                return {"ok": False, "erro": "Informe a chave Groq"}
            try:
                g = groq_sdk.Groq(api_key=chave)
                g.chat.completions.create(
                    model="llama-3.1-8b-instant", max_tokens=5,
                    messages=[{"role": "user", "content": "ok"}],
                )
            except Exception as e:
                return {"ok": False, "erro": f"Chave Groq inválida: {str(e)[:80]}"}
            _salvar_env("GROQ_API_KEY", chave)
            _salvar_env("PROVIDER", "groq")
            return {"ok": True, "provedor": "groq"}

        else:  # claude
            if not chave.startswith("sk-ant-api"):
                return {"ok": False, "erro": "Chave Claude deve começar com sk-ant-api03-"}
            try:
                c = anthropic.Anthropic(api_key=chave)
                c.messages.create(model="claude-haiku-4-5", max_tokens=10,
                                  messages=[{"role": "user", "content": "ok"}])
            except anthropic.AuthenticationError:
                return {"ok": False, "erro": "Chave rejeitada pela Anthropic (401)"}
            except Exception as e:
                return {"ok": False, "erro": f"Erro ao testar: {str(e)[:80]}"}
            _salvar_env("ANTHROPIC_API_KEY", chave)
            _salvar_env("PROVIDER", "claude")
            return {"ok": True, "provedor": "claude"}

    except Exception as e:
        return {"ok": False, "erro": str(e)}


@app.get("/", response_class=HTMLResponse)
async def root():
    with open("static/index.html", encoding="utf-8") as f:
        return f.read()


WEB_SEARCH_TOOL = {"type": "web_search_20250305", "name": "web_search", "max_uses": 2}


async def stream_groq(prompt: str, model: str = "llama-3.3-70b-versatile", max_tokens: int = 6000):
    """Gerador SSE usando Groq (gratuito)."""
    client = groq_client()
    stream = client.chat.completions.create(
        model=model,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
        stream=True,
    )
    for chunk in stream:
        delta = chunk.choices[0].delta.content or ""
        if delta:
            yield {"data": json.dumps({"token": delta})}
    yield {"data": json.dumps({"done": True})}


async def stream_claude(prompt: str, max_tokens: int = 8000):
    """Gerador SSE usando Claude Sonnet (pago)."""
    client = claude_client()
    with client.messages.stream(
        model="claude-sonnet-4-6",
        max_tokens=max_tokens,
        tools=[WEB_SEARCH_TOOL],
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        for text in stream.text_stream:
            yield {"data": json.dumps({"token": text})}
    yield {"data": json.dumps({"done": True})}


@app.post("/analisar")
async def analisar(request: Request):
    dados = await request.json()
    prompt = construir_prompt(dados)

    if get_provider() == "groq":
        return EventSourceResponse(stream_groq(prompt, max_tokens=6000))
    return EventSourceResponse(stream_claude(prompt, max_tokens=8000))


@app.post("/analisar-viabilidade")
async def analisar_viabilidade(request: Request):
    """Análise focada em viabilidade farmacotécnica com streaming."""
    dados = await request.json()

    componentes = dados.get("componentes", [])
    qtd_unidade = float(dados.get("qtd_por_unidade") or 500)
    unidade     = dados.get("unidade_medida", "mg")
    upd         = int(dados.get("unidades_por_dose") or 1)
    dpd         = int(dados.get("doses_por_dia") or 1)
    dose_diaria = upd * dpd * qtd_unidade

    comp_texto = "\n".join(
        f"  - {c['nome']} ({c.get('tipo','?')}): {c.get('concentracaoDisplay') or str(c.get('percentual','?')) + '%'}"
        + (f" — {c['funcao']}" if c.get('funcao') else "")
        for c in componentes
    )

    prompt = f"""Você é um farmacêutico industrial especialista em tecnologia farmacêutica e físico-química de formulações.

{FONTES_OFICIAIS}

Realize uma análise detalhada de **viabilidade farmacotécnica** da formulação abaixo em português, com base exclusivamente em fontes oficiais (Farmacopeia Brasileira, USP, Ph.Eur., literatura peer-reviewed).

## FORMULAÇÃO

- **Forma farmacêutica:** {dados.get("forma_farmaceutica", "Cápsula")}
- **Quantidade por unidade:** {qtd_unidade} {unidade}
- **Posologia:** {upd} unidade(s)/dose · {dpd} dose(s)/dia → dose diária total: {dose_diaria:.4f} {unidade}

### Componentes:
{comp_texto}

---

## ANÁLISE DE VIABILIDADE FARMACOTÉCNICA

Forneça análise técnica completa cobrindo obrigatoriamente:

### 1. 🔬 COMPATIBILIDADE FÍSICO-QUÍMICA
- Interações físicas entre os componentes (ex: eutéticos, higroscopicidade, eletrostática)
- Interações químicas (oxidação, hidrólise, complexação, reações ácido-base)
- pH e pKa relevantes
- Estabilidade de cada ativo nas condições de processo
- Conclusão: compatível / incompatível / requer cuidados especiais

### 2. 🏭 TÉCNICA DE FABRICAÇÃO RECOMENDADA
- Método indicado (mistura direta, granulação úmida, granulação seca, encapsulação direta, etc.)
- Justificativa com base nas características dos componentes
- Parâmetros críticos de processo (temperatura, umidade relativa, velocidade de mistura)
- Equipamentos necessários
- Etapas sequenciais do processo

### 3. ⚡ PROBLEMAS ESPERADOS NO PROCESSAMENTO
- Dificuldades de fluxo/escoamento (ângulo de repouso esperado)
- Segregação de partículas
- Compressibilidade (se aplicável)
- Higroscopicidade e sensibilidade à umidade
- Sensibilidade à temperatura e luz
- Problemas específicos de encapsulação/compressão

### 4. 🧪 ESTABILIDADE DA FORMULAÇÃO
- Prazo de validade estimado com base em dados da literatura
- Condições de armazenamento recomendadas (ICH Q1A)
- Estudos de estabilidade necessários (acelerado, longa duração, fotólise)
- Embalagem primária recomendada e justificativa
- Pontos críticos de degradação

### 5. 💊 BIODISPONIBILIDADE E LIBERAÇÃO
- Biodisponibilidade esperada de cada ativo
- Fatores que afetam a absorção (pH, solubilidade, tamanho de partícula, efeito de primeira passagem)
- Perfil de dissolução esperado
- Necessidade de tecnologias especiais (micronização, ciclodextrinas, lipossomas, etc.)

### 6. ✅ PARECER FINAL DE VIABILIDADE
- **Viável / Viável com ressalvas / Não viável**
- Resumo dos principais riscos farmacotécnicos
- Recomendações prioritárias antes de escalonamento industrial
- Testes de pré-formulação necessários

Cite referências específicas (Farmacopeia, USP, artigos) para cada afirmação técnica relevante."""

    if get_provider() == "groq":
        return EventSourceResponse(stream_groq(prompt, max_tokens=5000))
    return EventSourceResponse(stream_claude(prompt, max_tokens=6000))


def _chat_json(prompt: str, max_tokens: int = 800) -> str:
    """Chama o provedor configurado e retorna texto (para endpoints JSON não-stream)."""
    if get_provider() == "groq":
        client = groq_client()
        resp = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.choices[0].message.content or "{}"
    else:
        client = claude_client()
        msg = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return next((b.text for b in msg.content if getattr(b, "type", "") == "text"), "{}")


@app.post("/sugerir-forma")
async def sugerir_forma(request: Request):
    """Sugere a forma farmacêutica mais adequada com base na indicação e literatura."""
    try:
        dados = await request.json()
        indicacao = dados.get("indicacao", "")

        prompt = f"""Você é um especialista em farmácia industrial e tecnologia farmacêutica.

Com base na indicação terapêutica abaixo, sugira a forma farmacêutica mais adequada segundo a literatura científica e as boas práticas farmacêuticas.

**Indicação:** {indicacao}

Responda APENAS com JSON válido:
{{
  "forma": "nome da forma farmacêutica recomendada",
  "qtd_por_unidade": número (quantidade típica por unidade),
  "unidade_medida": "mg | mcg | mL | UI | g | etc.",
  "justificativa": "justificativa técnica em 1-2 frases citando a fonte (Farmacopeia, USP, literatura)",
  "alternativas": ["forma alternativa 1", "forma alternativa 2"],
  "vantagens": "principais vantagens desta forma para a indicação"
}}

Responda APENAS com o JSON."""

        import re
        texto = _chat_json(prompt, max_tokens=800)
        match = re.search(r'\{[\s\S]*\}', texto)
        if match:
            texto = match.group(0)
        return json.loads(texto)
    except Exception as e:
        return {"erro": str(e)}


@app.post("/sugerir-excipientes")
async def sugerir_excipientes(request: Request):
    """Sugere excipientes com base nos ativos e forma farmacêutica."""
    dados = await request.json()

    ativos = [c for c in dados.get("componentes", []) if c["tipo"] == "ativo"]
    qtd_unidade = float(dados.get("qtd_por_unidade") or dados.get("peso_unidade_mg") or 500)
    unidade = dados.get("unidade_medida", "mg")

    def fmt_ativo(c):
        conc = c.get("concentracaoDisplay") or f"{c.get('percentual', '?')}%"
        return f"  - {c['nome']}: {conc}"

    ativos_texto = "\n".join(fmt_ativo(c) for c in ativos)
    perc_ativos  = sum(float(c["percentual"]) for c in ativos if c.get("unidade") == "%" and c.get("percentual"))

    prompt = f"""Você é um farmacêutico industrial especialista em tecnologia farmacêutica.

{FONTES_OFICIAIS}

Com base nos princípios ativos abaixo, sugira os excipientes mais adequados para a formulação.

**Forma farmacêutica:** {dados.get("forma_farmaceutica", "Cápsula")}
**Quantidade por unidade:** {qtd_unidade} {unidade}
**Quantidade de unidades:** {dados.get("quantidade_unidades", 1000)}

**Princípios ativos:**
{ativos_texto}

**Percentual disponível para excipientes (base 100%):** {100 - perc_ativos:.2f}%

Responda em formato JSON válido com a seguinte estrutura exata:
{{
  "excipientes": [
    {{
      "nome": "nome do excipiente",
      "percentual": número,
      "tipo": "excipiente",
      "funcao": "função farmacotécnica",
      "justificativa": "por que é adequado para estes ativos"
    }}
  ],
  "tecnica_fabricacao": "técnica recomendada",
  "observacoes": "observações importantes"
}}

Os percentuais dos excipientes devem somar exatamente {100 - perc_ativos:.2f}%.
Sugira apenas excipientes comprovadamente compatíveis com os ativos listados.
Responda APENAS com o JSON, sem texto adicional."""

    import re
    texto = _chat_json(prompt, max_tokens=2000)
    match = re.search(r'\{[\s\S]*\}', texto)
    if match:
        texto = match.group(0)

    try:
        resultado = json.loads(texto)
    except Exception:
        resultado = {"excipientes": [], "observacoes": "Erro ao processar sugestão."}

    return resultado


@app.post("/extrair-pdf")
async def extrair_pdf(file: UploadFile = File(...)):
    """Extrai dados de formulação de um PDF."""
    try:
        return await _extrair_pdf(file)
    except Exception as e:
        return {"erro": f"Erro ao processar PDF: {str(e)}"}


async def _extrair_pdf(file: UploadFile):
    client = claude_client()  # PDF/imagem sempre usa Claude (visão)

    pdf_bytes = await file.read()
    pdf_b64 = base64.standard_b64encode(pdf_bytes).decode("utf-8")

    prompt = """Analise este documento PDF e identifique todas as formulações farmacêuticas ou suplementares possíveis descritas nele.
Se o documento contiver mais de uma formulação, variação, opção ou receita, extraia todas elas.

Responda APENAS com um objeto JSON válido contendo uma lista de formulações no seguinte formato:
{
  "formulacoes": [
    {
      "nome_opcao": "Nome curto identificando esta fórmula específica (ex: 'Opção 1: Energético', 'Página 2 - Fórmula B')",
      "forma_farmaceutica": "string (ex: Cápsula, Comprimido, Sachê, Pomada/Creme, Solução oral, etc.)",
      "quantidade_unidades": número ou null,
      "peso_unidade_mg": número ou null,
      "indicacao": "string ou vazio",
      "componentes": [
        {
          "nome": "nome do componente",
          "percentual": número,
          "tipo": "ativo | excipiente | adjuvante"
        }
      ],
      "observacoes": "informações adicionais específicas desta formulação encontradas no PDF"
    }
  ]
}

Se algum campo não estiver no documento, use null ou valor padrão razoável.
Para os percentuais: se o documento tiver a quantidade em mg ou g por unidade/dose, estime/calcule o percentual em relação ao peso total da forma farmacêutica (ex: se a cápsula for de 500mg e tiver 250mg de ativo, o ativo representa 50%).
Responda APENAS com o JSON válido, sem texto explicativo, sem markdown (como ```json) ou qualquer introdução/conclusão."""

    msg = client.messages.create(
        model="claude-opus-4-8",
        max_tokens=4000,
        thinking={"type": "adaptive"},
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "document",
                    "source": {
                        "type": "base64",
                        "media_type": "application/pdf",
                        "data": pdf_b64,
                    },
                },
                {"type": "text", "text": prompt},
            ],
        }],
    )

    texto = next((b.text for b in msg.content if getattr(b, "type", "") == "text"), "{}")
    import re
    match = re.search(r'\{[\s\S]*\}', texto)
    if match:
        texto = match.group(0)

    try:
        resultado = json.loads(texto)
    except Exception:
        resultado = {"erro": "Não foi possível extrair dados do PDF."}

    return resultado


@app.post("/extrair-imagem")
async def extrair_imagem(file: UploadFile = File(...)):
    """Extrai dados de formulação de uma imagem (foto de rótulo, fórmula, receita, etc.)."""
    try:
        return await _extrair_imagem(file)
    except Exception as e:
        return {"erro": f"Erro ao processar imagem: {str(e)}"}


async def _extrair_imagem(file: UploadFile):
    client = claude_client()  # Imagem sempre usa Claude (visão)

    img_bytes = await file.read()
    img_b64 = base64.standard_b64encode(img_bytes).decode("utf-8")

    # Detecta media type: prioriza content_type enviado pelo browser, fallback por extensão
    media_type = file.content_type or ""
    if not media_type.startswith("image/"):
        ext = (file.filename or "").lower().rsplit(".", 1)[-1]
        media_types = {
            "jpg": "image/jpeg", "jpeg": "image/jpeg",
            "png": "image/png", "gif": "image/gif", "webp": "image/webp",
        }
        media_type = media_types.get(ext, "image/png")

    # Normaliza tipos não suportados pela API
    if media_type not in ("image/jpeg", "image/png", "image/gif", "image/webp"):
        media_type = "image/png"

    prompt = """Analise esta imagem (rótulo, embalagem, receita, fórmula manuscrita ou impressa) e identifique todas as formulações farmacêuticas ou suplementares possíveis descritas nela.
Se a imagem contiver mais de uma formulação, opção ou variação, extraia todas elas.

Responda APENAS com um objeto JSON válido contendo uma lista de formulações no seguinte formato:
{
  "formulacoes": [
    {
      "nome_opcao": "Nome curto identificando esta fórmula específica (ex: 'Fórmula 1', 'Fórmula da esquerda')",
      "forma_farmaceutica": "string (ex: Cápsula, Comprimido, Sachê, Pomada/Creme, etc.)",
      "quantidade_unidades": número ou null,
      "peso_unidade_mg": número ou null,
      "indicacao": "string ou vazio",
      "componentes": [
        {
          "nome": "nome do componente",
          "percentual": número,
          "tipo": "ativo | excipiente | adjuvante"
        }
      ],
      "observacoes": "informações adicionais específicas desta formulação encontradas na imagem"
    }
  ]
}

Se algum campo não estiver visível ou implícito, use null.
Para os percentuais: se os ingredientes estiverem em mg/g por dose, calcule o percentual em relação ao peso total da forma farmacêutica. Se o peso total não estiver indicado, estime com base em valores típicos de mercado.
Responda APENAS com o JSON válido, sem texto explicativo, sem markdown (como ```json) ou qualquer introdução/conclusão."""

    msg = client.messages.create(
        model="claude-opus-4-8",
        max_tokens=4000,
        thinking={"type": "adaptive"},
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": img_b64,
                    },
                },
                {"type": "text", "text": prompt},
            ],
        }],
    )

    texto = next((b.text for b in msg.content if getattr(b, "type", "") == "text"), "{}")
    import re
    match = re.search(r'\{[\s\S]*\}', texto)
    if match:
        texto = match.group(0)

    try:
        resultado = json.loads(texto)
    except Exception:
        resultado = {"erro": "Não foi possível extrair dados da imagem."}

    return resultado


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
