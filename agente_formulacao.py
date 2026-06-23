#!/usr/bin/env python3
"""
Agente de Planejamento Farmacêutico
Analisa formulações e fornece informações técnicas, regulatórias e de compra.
"""

import anthropic
import json
import re
import csv
import subprocess
import datetime


def limpar_texto(texto: str) -> str:
    """Remove caracteres de controle indesejados, preservando quebras de linha e tabulações."""
    # Remove control characters except \n, \r, \t
    texto_limpo = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', texto)
    return texto_limpo


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

    prompt = f"""Você é um consultor especialista em farmácia industrial e regulação farmacêutica brasileira (ANVISA). Responda com um tom profissional, consultivo e claro, evitando jargões desnecessários.

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

Forneça uma análise completa e detalhada cobrindo TODOS os seguintes tópicos.
**DIRETRIZ CRÍTICA:** NUNCA corte o texto. Forneça respostas completas e detalhadas para cada seção, garantindo que nenhuma informação seja truncada.

### 1. QUANTIDADES DE COMPRA
Para cada componente ativo (apresente **OBRIGATORIAMENTE** em formato de Tabela Markdown):
- Quantidade exata a comprar (com margem de perda de fabricação recomendada de 5-10%)
- Fornecedores típicos no Brasil (categorias/tipos)
- Forma de compra recomendada (granel, farmácia de manipulação, distribuidora)
- Condições de armazenamento e transporte

### 2. DOSAGEM POR UNIDADE - ATIVOS
Para cada princípio ativo presente (apresente **OBRIGATORIAMENTE** em formato de Tabela Markdown):
- Dose máxima recomendada por unidade (comprimido/cápsula/etc.) segundo literatura científica
- Dose mínima terapêutica eficaz por unidade
- Frequência de administração típica (vezes ao dia)
- Dose diária máxima total (DDD)
- Comparação com a dose calculada nesta formulação (adequada/alta/baixa)

### 3. RESTRIÇÕES POR FAIXA ETÁRIA
Para cada componente ativo (apresente **OBRIGATORIAMENTE** em formato de Tabela Markdown):
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

*Nota: Organize os dados estruturados rigorosamente em tabelas Markdown, certificando-se de não omitir nenhuma coluna solicitada. Essas tabelas serão extraídas automaticamente pelo sistema.*
Seja preciso, técnico e cite as legislações brasileiras vigentes quando aplicável.
Se algum componente for desconhecido ou não habitual em farmácias, sinalize claramente."""

    return prompt


def analisar_formulacao(dados: dict) -> str:
    """Envia para o Claude e exibe a análise com streaming. Retorna o texto gerado."""
    client = anthropic.Anthropic()

    prompt = construir_prompt(dados)

    print("\n" + "=" * 60)
    print("  ANALISANDO FORMULAÇÃO...")
    print("  (Aguarde — análise completa em andamento)")
    print("=" * 60 + "\n")

    texto_completo = ""
    with client.messages.stream(
        model="claude-opus-4-8",
        max_tokens=16000,
        thinking={"type": "adaptive"},
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        for text in stream.text_stream:
            print(text, end="", flush=True)
            texto_completo += text

    print("\n\n" + "=" * 60)
    print("  ANÁLISE CONCLUÍDA")
    print("=" * 60)
    
    return texto_completo


def salvar_relatorio(dados: dict, texto_gerado: str):
    """Pergunta se deseja salvar, extrai tabelas em CSV e salva o relatório em Markdown."""
    salvar = input("\nDeseja salvar este relatório e suas planilhas? (s/n): ").strip().lower()
    if salvar != "s":
        return

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    nome_arquivo_md = f"relatorio_formulacao_{timestamp}.md"

    print(f"\nExtraindo tabelas e salvando arquivos...")
    
    # Higieniza o texto para remover caracteres problemáticos
    texto_limpo = limpar_texto(texto_gerado)

    # Extrair tabelas Markdown
    linhas = texto_limpo.split('\n')
    tabelas = []
    tabela_atual = []
    em_tabela = False
    
    for linha in linhas:
        # Verifica se a linha se parece com uma linha de tabela Markdown (tem pipes e não é um título markdown)
        if re.search(r'\|.*\|', linha) and not re.search(r'^[#*\-]\s', linha.strip()):
            em_tabela = True
            tabela_atual.append(linha.strip())
        else:
            if em_tabela:
                # Fim da tabela atual
                if len(tabela_atual) > 2: # Exige pelo menos cabeçalho, separador e 1 linha de dados
                    tabelas.append(tabela_atual)
                tabela_atual = []
                em_tabela = False
                
    if em_tabela and len(tabela_atual) > 2:
        tabelas.append(tabela_atual)

    # Salva as tabelas em CSV
    count_tabela = 1
    for tabela in tabelas:
        nome_csv = f"relatorio_formulacao_{timestamp}_tabela{count_tabela}.csv"
        try:
            # utf-8-sig adiciona o BOM para que o Excel abra os acentos corretamente
            with open(nome_csv, "w", encoding="utf-8-sig", newline="") as f:
                writer = csv.writer(f, delimiter=';')
                for linha in tabela:
                    # Ignorar linha de separação Markdown tipo |---|---|
                    if re.match(r'^[\s\|:-]+$', linha):
                        continue
                    # Limpar os pipes das pontas e dividir as colunas
                    linha = linha.strip('| ')
                    colunas = [col.strip() for col in linha.split('|')]
                    writer.writerow(colunas)
            print(f"✓ Planilha salva: {nome_csv}")
            count_tabela += 1
        except Exception as e:
            print(f"Erro ao salvar tabela {count_tabela}: {e}")

    # Prepara o cabeçalho do arquivo Markdown
    cabecalho = f"""# RELATÓRIO DE PLANEJAMENTO FARMACÊUTICO
**Gerado em:** {datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")}
**Forma farmacêutica:** {dados["forma_farmaceutica"]}
**Quantidade:** {dados["quantidade_unidades"]} unidades
**Peso/unidade:** {dados["peso_unidade_mg"]} mg
**Indicação:** {dados["indicacao"]}

### Componentes:
"""
    for c in dados["componentes"]:
        cabecalho += f"- **{c['nome']}** ({c['tipo']}): {c['percentual']}%\n"

    cabecalho += "\n---\n\n"

    try:
        with open(nome_arquivo_md, "w", encoding="utf-8") as f:
            f.write(cabecalho + texto_limpo)
        print(f"✓ Relatório detalhado salvo em: {nome_arquivo_md}")
    except Exception as e:
        print(f"Erro ao salvar o arquivo Markdown: {e}")


def sincronizar_github():
    """Executa comandos git para sincronizar com o GitHub."""
    sincronizar = input("\nDeseja sincronizar os novos relatórios com o repositório GitHub? (s/n): ").strip().lower()
    if sincronizar != "s":
        return
        
    print("\nSincronizando com GitHub...")
    try:
        # Adicionar arquivos
        subprocess.run(["git", "add", "."], check=True, capture_output=True, text=True)
        
        # Commit
        mensagem_commit = f"Adiciona novos relatórios gerados em {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        resultado_commit = subprocess.run(["git", "commit", "-m", mensagem_commit], capture_output=True, text=True)
        
        # Se não houver nada para commitar, exibe a mensagem
        if "nothing to commit" in resultado_commit.stdout or "nada a fazer" in resultado_commit.stdout or "nothing added" in resultado_commit.stdout:
            print("Nenhum arquivo novo ou alterado para fazer commit.")
            return

        # Push
        subprocess.run(["git", "push", "origin", "main"], check=True, capture_output=True, text=True)
        print("✓ Relatórios sincronizados com o repositório GitHub com sucesso!")
        
    except subprocess.CalledProcessError as e:
        print("\nErro durante a sincronização com o GitHub.")
        print(f"Comando falhou: {' '.join(e.cmd)}")
        if e.stderr:
            print(f"Detalhes do erro: {e.stderr.strip()}")
    except FileNotFoundError:
        print("\nErro: O comando 'git' não foi encontrado. Certifique-se de que o Git está instalado e no PATH.")
    except Exception as e:
        print(f"\nErro inesperado ao sincronizar com GitHub: {e}")


def main():
    print("\n" + "=" * 60)
    print("  AGENTE DE PLANEJAMENTO FARMACÊUTICO")
    print("  Powered by Claude Opus 4.8 (Anthropic)")
    print("=" * 60)

    while True:
        dados = coletar_formulacao()
        texto_gerado = analisar_formulacao(dados)
        salvar_relatorio(dados, texto_gerado)
        sincronizar_github()

        continuar = input(
            "\nDeseja analisar outra formulação? (s/n): "
        ).strip().lower()
        if continuar != "s":
            break

    print("\nEncerrando o agente. Até logo!\n")


if __name__ == "__main__":
    main()
