# Primeiros passos
*Esta página é uma tradução da [página em inglês](../../getting_started.md); correções são bem-vindas.*

Modelly é um framework modular para construir, analisar e visualizar modelos baseados em agentes.

**Modelos baseados em agentes** são simulações computacionais com várias entidades (os agentes) que agem e interagem entre si de acordo com o comportamento programado. Os agentes podem representar células vivas, animais, pessoas e até organizações inteiras ou entidades abstratas. Às vezes, entendemos como os componentes individuais de um sistema se comportam e queremos ver que comportamentos e efeitos surgem, no nível do sistema, da interação entre eles. Outras vezes, temos uma boa ideia de como o sistema se comporta como um todo e queremos descobrir que comportamentos individuais o explicam. Ou queremos ver como fazer os agentes cooperarem ou competirem da forma mais eficaz. Ou simplesmente queremos construir um brinquedo divertido com pontinhos coloridos se movendo.

## Visão geral
Se quiser ter uma ideia geral dos recursos e da estrutura do Modelly, comece aqui:

- [Visão geral da biblioteca MODELLY](../../overview): conheça os conceitos e componentes centrais do Modelly.

## Tutoriais
Se quiser aprender passo a passo a construir modelos baseados em agentes com o Modelly, siga estes tutoriais:

- [Criando seu primeiro modelo](../../tutorials/0_first_model): aprenda a criar seu primeiro modelo Modelly.
- [AgentSet](../../tutorials/1_agentset): aprenda a gerenciar agentes de forma mais eficaz com o AgentSet do Modelly.
- [Ativação de agentes](../../tutorials/2_agent_activation): aprenda diferentes formas de ativar agentes com `do`, `shuffle_do` e `map`, cobrindo os padrões de ativação aleatória, sequencial, simultânea, em etapas, por tipo e condicional.
- [Agendamento de eventos](../../tutorials/3_event_scheduling): aprenda a agendar eventos e a gerenciar o tempo no seu modelo Modelly.
- [Adicionando espaço](../../tutorials/4_adding_space): aprenda a adicionar espaço ao seu modelo Modelly e a entender a arquitetura de espaços do Modelly.
- [Coletando dados](../../tutorials/5_collecting_data): aprenda a coletar dados no nível do modelo e dos agentes com o DataCollector do Modelly.
- [Visualização básica](../../tutorials/6_visualization_basic): aprenda a construir um painel interativo com o módulo de visualização do Modelly.
- [Visualização dinâmica de agentes](../../tutorials/7_visualization_dynamic_agents): aprenda a representar dinamicamente seus agentes no painel interativo.
- [Visualização com SpaceRenderer](../../tutorials/8_visualization_rendering_with_space_renderer): aprenda a usar o SpaceRenderer ao máximo para aprimorar suas visualizações.
- [Visualização de camadas de propriedades](../../tutorials/9_visualization_property_layer_visualization): aprenda a visualizar camadas de propriedades no Modelly.
- [Componentes de visualização personalizados](../../tutorials/10_visualization_custom): aprenda a adicionar componentes visuais personalizados ao seu painel interativo.
- [Simulação de eventos discretos](../../tutorials/11_discrete_event_simulation): aprenda a construir um modelo puramente orientado a eventos com `schedule_event` e a validá-lo com a teoria das filas.
- [Modelos híbridos ABM-DEVS](../../tutorials/12_hybrid_abm_devs): aprenda a combinar a ativação de agentes baseada em `step()` com eventos agendados em um modelo epidêmico espacial.

## Seu próprio projeto
- [Usando o Modelly no seu projeto](../../using_modelly_in_your_project): de uma pasta vazia a um modelo reprodutível e medido, que vive no seu próprio repositório.
- [Iniciando um projeto](../../new_project): `modelly new` escreve um projeto com semente, testes e verificação desde o primeiro commit.
- [Boas práticas do Modelly](../../best-practices): um panorama de dicas e orientações para usar o Modelly.

## Cursos e tutoriais por área
- [Curso](../../course/index): doze sessões que levam uma turma de um primeiro modelo a um estudo próprio, validado e reprodutível.
- [Tutoriais por área](../../tutorials/domains/index): um tutorial por área, cada um construído sobre um modelo do zoo.

## Vindo de outra ferramenta
- [Migrando do Mesa](../../migrating_from_mesa): um mapeamento construção a construção e um codemod, `python -m modelly.migrate`, que reescreve as partes mecânicas e relata o restante.
- [Do NetLogo](../../netlogo): `python -m modelly.netlogo` traduz um modelo `.nlogo` em um módulo Python que você pode executar, testar e verificar.
- [Do R e do Julia](../../r_and_julia): leia os resultados Parquet do Modelly no R e no Julia, e controle um modelo a partir do R.

## Exemplos
O Modelly vem com uma coleção de modelos de exemplo. São ABMs clássicos; se você já conhece ABMs e quer ter uma ideia rápida de como o MODELLY funciona, esses exemplos são um ótimo ponto de partida. Você os encontra [aqui](../../examples).

## Mais recursos
Para explorar mais o Modelly e seus recursos, estão disponíveis:

### Documentação da API
- [Referência da API do Modelly](../../apis/api_main.md): documentação detalhada das classes e funções do Modelly, uma página por pacote (`modelly.core`, `modelly.space`, `modelly.time`, `modelly.data`, `modelly.behaviour`, `modelly.scenarios`, `modelly.batch`, `modelly.viz`).

### Código-fonte e desenvolvimento
- [Repositório do Modelly no GitHub](https://github.com/RemiPelloux/Modelly): acesse todo o código-fonte do Modelly, contribua para o seu desenvolvimento ou relate problemas.
- [Notas de versão do Modelly](https://github.com/RemiPelloux/Modelly/releases): veja o registro detalhado de mudanças do Modelly, com todas as versões anteriores e seus recursos.

### Comunidade e suporte
- [GitHub Discussions do Modelly](https://github.com/RemiPelloux/Modelly/discussions): participe das discussões, faça perguntas e converse com outros usuários do Modelly.

Divirta-se modelando com o Modelly, e fique à vontade para entrar em contato!
