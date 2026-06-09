#!/usr/bin/env python3
"""
Agente de Planejamento Farmacêutico
Analisa formulações e fornece informações técnicas, regulatórias e de compra.
"""

import anthropic
import json


def coletar_formulacao() -> dict:
    """Coleta os dados da formulação pelo terminal."""
    print("\n" + "=" * 60)
    print("  AGENTE DE PLANEJAMENTO FARMACÊUTICO")
    print("=" * 60)
    print("\nBem-vindo! Vamos planejar sua formulação.\n")

    # Forma farmacêutica
    print("Formas farmacêuticas disponíveis:")
    formas = {
        "1": "Cápsula",
        "2": "Comprimido",
        "3": "Comprimido revestido",
        "4": "Sachê",
        "5": "Solução oral",
        "6": "Suspensão oral",
        "7": "Pomada/Creme",
        "8": "Supositório",
        "9": "Injetável",
        "10": "Outra (especificar)",
    }
    for k, v in formas.items():
        print(f"  {k}. {v}")

    while True:
        escolha = input("\nEscolha a forma farmacêutica (número): ").strip()
        if escolha in formas:
            if escolha == "10":
                forma = input("Especifique a forma farmacêutica: ").strip()
            else:
                forma = formas[escolha]
            break
        print("Opção inválida. Tente novamente.")

    # Quantidade de unidades
    while True:
        try:
            qtd_str = input(f"\nQuantas unidades de {forma} deseja produzir? ").strip()
            quantidade = int(qtd_str)
            if quantidade <= 0:
                raise ValueError
            break
        except ValueError:
            print("Por favor, insira um número inteiro positivo.")

    # Peso/volume por unidade
    while True:
        try:
            peso_str = input(
                f"\nPeso/volume por unidade em mg (ex: 500 para cápsula de 500mg): "
            ).strip()
            peso_unidade = float(peso_str)
            if peso_unidade <= 0:
                raise ValueError
            break
        except ValueError:
            print("Por favor, insira um número válido.")

    # Componentes da formulação
    print("\n" + "-" * 40)
    print("COMPONENTES DA FORMULAÇÃO")
    print("-" * 40)
    print(
        "Informe cada componente com seu percentual (% p/p)."
    )
    print("A soma dos percentuais deve ser 100%.\n")

    componentes = []
    total_percentual = 0.0

    while True:
        print(f"\nComponente #{len(componentes) + 1}")
        nome = input("Nome do componente (ou 'fim' para encerrar): ").strip()
        if nome.lower() == "fim":
            if not componentes:
                print("Adicione pelo menos um componente.")
                continue
            if abs(total_percentual - 100.0) > 0.01:
                print(
                    f"Atenção: total atual = {total_percentual:.2f}%. "
                    f"Faltam {100 - total_percentual:.2f}% para 100%."
                )
                confirmar = input("Deseja continuar mesmo assim? (s/n): ").strip().lower()
                if confirmar != "s":
                    continue
            break

        while True:
            try:
                perc_str = input(f"Percentual de {nome} (%): ").strip()
                percentual = float(perc_str)
                if percentual <= 0 or percentual > 100:
                    raise ValueError
                break
            except ValueError:
                print("Insira um percentual válido (0-100).")

        tipo = input(
            f"Tipo de {nome} [ativo/excipiente/adjuvante]: "
        ).strip().lower() or "ativo"

        componentes.append(
            {"nome": nome, "percentual": percentual, "tipo": tipo}
        )
        total_percentual += percentual
        print(f"  ✓ {nome}: {percentual}% | Total acumulado: {total_percentual:.2f}%")

        if abs(total_percentual - 100.0) < 0.01:
            print("\n✓ Percentuais somam 100%. Formulação completa!")
            break

    # Indicação terapêutica (opcional)
    indicacao = input(
        "\nIndicação terapêutica pretendida (ex: analgésico, vitamínico, deixe vazio para análise geral): "
    ).strip()

    return {
        "forma_farmaceutica": forma,
        "quantidade_unidades": quantidade,
        "peso_unidade_mg": peso_unidade,
        "componentes": componentes,
        "indicacao": indicacao or "não especificada",
    }


def construir_prompt(dados: dict) -> str:
    """Monta o prompt completo para análise farmacêutica."""
    componentes_texto = "\n".join(
        f"  - {c['nome']} ({c['tipo']}): {c['percentual']}%"
        for c in dados["componentes"]
    )

    peso_total_lote = (
        dados["quantidade_unidades"] * dados["peso_unidade_mg"]
    ) / 1000  # em gramas

    quantidades_por_componente = []
    for c in dados["componentes"]:
        qtd_g = (c["percentual"] / 100) * peso_total_lote
        qtd_kg = qtd_g / 1000
        quantidades_por_componente.append(
            f"  - {c['nome']}: {qtd_g:.2f} g ({qtd_kg:.4f} kg)"
        )
    qtd_texto = "\n".join(quantidades_por_componente)

    prompt = f"""Você é um especialista em farmácia industrial e regulação farmacêutica brasileira (ANVISA).

Analise a seguinte formulação farmacêutica e forneça um relatório técnico completo em português:

## DADOS DA FORMULAÇÃO

- **Forma farmacêutica:** {dados["forma_farmaceutica"]}
- **Quantidade a produzir:** {dados["quantidade_unidades"]} unidades
- **Peso/volume por unidade:** {dados["peso_unidade_mg"]} mg
- **Peso total do lote:** {peso_total_lote:.2f} g ({peso_total_lote/1000:.4f} kg)
- **Indicação pretendida:** {dados["indicacao"]}

### Componentes da formulação:
{componentes_texto}

### Quantidades calculadas para o lote:
{qtd_texto}

---

## RELATÓRIO SOLICITADO

Forneça uma análise completa e detalhada cobrindo TODOS os seguintes tópicos:

### 1. QUANTIDADES DE COMPRA
Para cada componente ativo, especifique:
- Quantidade exata a comprar (com margem de perda de fabricação recomendada de 5-10%)
- Fornecedores típicos no Brasil (categorias/tipos)
- Forma de compra recomendada (granel, farmácia de manipulação, distribuidora)
- Condições de armazenamento e transporte

### 2. DOSAGEM POR UNIDADE - ATIVOS
Para cada princípio ativo presente, informe:
- Dose máxima recomendada por unidade (comprimido/cápsula/etc.) segundo literatura científica
- Dose mínima terapêutica eficaz por unidade
- Frequência de administração típica (vezes ao dia)
- Dose diária máxima total (DDD)
- Comparação com a dose calculada nesta formulação (adequada/alta/baixa)

### 3. RESTRIÇÕES POR FAIXA ETÁRIA
Para cada componente ativo:
- Uso pediátrico: idade mínima permitida e ajuste de dose por kg
- Uso geriátrico: ajustes necessários
- Contraindicações por faixa etária
- Uso em gestantes (categoria de risco FDA/ANVISA)
- Uso em lactantes

### 4. VIABILIDADE FARMACOTÉCNICA
Analise:
- Compatibilidade físico-química entre os componentes
- Estabilidade da formulação (temperatura, umidade, luz)
- Adequação dos excipientes para a forma farmacêutica escolhida
- Técnica de fabricação recomendada (mistura direta, granulação úmida/seca, etc.)
- Possíveis problemas de processamento
- Biodisponibilidade esperada

### 5. INCOMPATIBILIDADES FARMACOTÉCNICAS
Identifique:
- Incompatibilidades físicas entre os componentes
- Incompatibilidades químicas (reações, degradação)
- Incompatibilidades farmacológicas (interações entre ativos)
- Soluções e alternativas para cada incompatibilidade identificada

### 6. REGULAÇÃO ANVISA - BRASIL
Informe:
- Categoria regulatória do produto (OTC, similar, genérico, novo, fitoterápico, etc.)
- Necessidade de registro ou notificação na ANVISA
- RDC e normativas aplicáveis
- Classificação da venda (venda livre, sob prescrição, com retenção de receita)
- Necessidade de responsável técnico farmacêutico
- Exigências de Boas Práticas de Fabricação (BPF/GMP)
- Lista de substâncias controladas: verificar se algum componente está nas portarias SVS/MS

### 7. RESTRIÇÕES COMERCIAIS NO BRASIL
Informe:
- Necessidade de autorização especial de funcionamento
- Restrições para venda online
- Requisitos de rotulagem obrigatória
- Necessidade de bula
- Embalagens autorizadas
- Restrições de propaganda e publicidade
- Possíveis impedimentos para comercialização direta ao consumidor

### 8. RECOMENDAÇÕES FINAIS
- Parecer geral sobre a viabilidade da formulação
- Principais pontos de atenção
- Próximos passos recomendados para registro/fabricação
- Alertas de segurança relevantes

---

Seja preciso, técnico e cite as legislações brasileiras vigentes quando aplicável.
Se algum componente for desconhecido ou não habitual em farmácias, sinalize claramente."""

    return prompt


def analisar_formulacao(dados: dict):
    """Envia para o Claude e exibe a análise com streaming."""
    client = anthropic.Anthropic()

    prompt = construir_prompt(dados)

    print("\n" + "=" * 60)
    print("  ANALISANDO FORMULAÇÃO...")
    print("  (Aguarde — análise completa em andamento)")
    print("=" * 60 + "\n")

    with client.messages.stream(
        model="claude-opus-4-8",
        max_tokens=16000,
        thinking={"type": "adaptive"},
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        for text in stream.text_stream:
            print(text, end="", flush=True)

    print("\n\n" + "=" * 60)
    print("  ANÁLISE CONCLUÍDA")
    print("=" * 60)


def salvar_relatorio(dados: dict):
    """Pergunta se deseja salvar e salva em arquivo texto."""
    salvar = input("\nDeseja salvar este relatório em arquivo? (s/n): ").strip().lower()
    if salvar != "s":
        return

    import datetime

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    nome_arquivo = f"relatorio_formulacao_{timestamp}.txt"

    client = anthropic.Anthropic()
    prompt = construir_prompt(dados)

    print(f"\nSalvando em {nome_arquivo}...")

    with client.messages.stream(
        model="claude-opus-4-8",
        max_tokens=16000,
        thinking={"type": "adaptive"},
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        conteudo = stream.get_final_message()

    texto = ""
    for bloco in conteudo.content:
        if hasattr(bloco, "text"):
            texto += bloco.text

    cabecalho = f"""RELATÓRIO DE PLANEJAMENTO FARMACÊUTICO
Gerado em: {datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")}
Forma farmacêutica: {dados["forma_farmaceutica"]}
Quantidade: {dados["quantidade_unidades"]} unidades
Peso/unidade: {dados["peso_unidade_mg"]} mg
Indicação: {dados["indicacao"]}

Componentes:
"""
    for c in dados["componentes"]:
        cabecalho += f"  - {c['nome']} ({c['tipo']}): {c['percentual']}%\n"

    cabecalho += "\n" + "=" * 60 + "\n\n"

    with open(nome_arquivo, "w", encoding="utf-8") as f:
        f.write(cabecalho + texto)

    print(f"✓ Relatório salvo em: {nome_arquivo}")


def main():
    print("\n" + "=" * 60)
    print("  AGENTE DE PLANEJAMENTO FARMACÊUTICO")
    print("  Powered by Claude Opus 4.8 (Anthropic)")
    print("=" * 60)

    while True:
        dados = coletar_formulacao()
        analisar_formulacao(dados)

        continuar = input(
            "\nDeseja analisar outra formulação? (s/n): "
        ).strip().lower()
        if continuar != "s":
            break

    print("\nEncerrando o agente. Até logo!\n")


if __name__ == "__main__":
    main()
