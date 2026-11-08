# Primeiros passos

*Esta página é uma tradução da [página em inglês](https://remipelloux.github.io/Modelly/getting_started.html); correções são bem-vindas.*

Modelly é um framework modular para construir, analisar e visualizar modelos baseados em agentes.

**Modelos baseados em agentes** são simulações computacionais com várias entidades (os agentes) que agem e interagem entre si de acordo com o comportamento programado. Os agentes podem representar células vivas, animais, pessoas e até organizações inteiras ou entidades abstratas. Às vezes, entendemos como os componentes individuais de um sistema se comportam e queremos ver que comportamentos e efeitos surgem, no nível do sistema, da interação entre eles. Outras vezes, temos uma boa ideia de como o sistema se comporta como um todo e queremos descobrir que comportamentos individuais o explicam. Ou queremos ver como fazer os agentes cooperarem ou competirem da forma mais eficaz. Ou simplesmente queremos construir um brinquedo divertido com pontinhos coloridos se movendo.

## Visão geral

Se quiser ter uma ideia geral dos recursos e da estrutura do Modelly, comece aqui:

- [Visão geral da biblioteca MODELLY](https://remipelloux.github.io/Modelly/overview.html): conheça os conceitos e componentes centrais do Modelly.

## Tutoriais

Se quiser aprender passo a passo a construir modelos baseados em agentes com o Modelly, siga estes tutoriais:

- [Criando seu primeiro modelo](https://remipelloux.github.io/Modelly/tutorials/0_first_model.html): aprenda a criar seu primeiro modelo Modelly.
- [AgentSet](https://remipelloux.github.io/Modelly/tutorials/1_agentset.html): aprenda a gerenciar agentes de forma mais eficaz com o AgentSet do Modelly.
- [Ativação de agentes](https://remipelloux.github.io/Modelly/tutorials/2_agent_activation.html): aprenda diferentes formas de ativar agentes com `do`, `shuffle_do` e `map`, cobrindo os padrões de ativação aleatória, sequencial, simultânea, em etapas, por tipo e condicional.
- [Agendamento de eventos](https://remipelloux.github.io/Modelly/tutorials/3_event_scheduling.html): aprenda a agendar eventos e a gerenciar o tempo no seu modelo Modelly.
- [Adicionando espaço](https://remipelloux.github.io/Modelly/tutorials/4_adding_space.html): aprenda a adicionar espaço ao seu modelo Modelly e a entender a arquitetura de espaços do Modelly.
- [Coletando dados](https://remipelloux.github.io/Modelly/tutorials/5_collecting_data.html): aprenda a coletar dados no nível do modelo e dos agentes com o DataCollector do Modelly.
- [Visualização básica](https://remipelloux.github.io/Modelly/tutorials/6_visualization_basic.html): aprenda a construir um painel interativo com o módulo de visualização do Modelly.
- [Visualização dinâmica de agentes](https://remipelloux.github.io/Modelly/tutorials/7_visualization_dynamic_agents.html): aprenda a representar dinamicamente seus agentes no painel interativo.
- [Visualização com SpaceRenderer](https://remipelloux.github.io/Modelly/tutorials/8_visualization_rendering_with_space_renderer.html): aprenda a usar o SpaceRenderer ao máximo para aprimorar suas visualizações.
- [Visualização de camadas de propriedades](https://remipelloux.github.io/Modelly/tutorials/9_visualization_property_layer_visualization.html): aprenda a visualizar camadas de propriedades no Modelly.
- [Componentes de visualização personalizados](https://remipelloux.github.io/Modelly/tutorials/10_visualization_custom.html): aprenda a adicionar componentes visuais personalizados ao seu painel interativo.
- [Simulação de eventos discretos](https://remipelloux.github.io/Modelly/tutorials/11_discrete_event_simulation.html): aprenda a construir um modelo puramente orientado a eventos com `schedule_event` e a validá-lo com a teoria das filas.
- [Modelos híbridos ABM-DEVS](https://remipelloux.github.io/Modelly/tutorials/12_hybrid_abm_devs.html): aprenda a combinar a ativação de agentes baseada em `step()` com eventos agendados em um modelo epidêmico espacial.

## Seu próprio projeto

- [Usando o Modelly no seu projeto](https://remipelloux.github.io/Modelly/using_modelly_in_your_project.html): de uma pasta vazia a um modelo reprodutível e medido, que vive no seu próprio repositório.
- [Iniciando um projeto](https://remipelloux.github.io/Modelly/new_project.html): `modelly new` escreve um projeto com semente, testes e verificação desde o primeiro commit.
- [Boas práticas do Modelly](https://remipelloux.github.io/Modelly/best-practices.html): um panorama de dicas e orientações para usar o Modelly.

## Cursos e tutoriais por área

- [Curso](https://remipelloux.github.io/Modelly/course/index.html): doze sessões que levam uma turma de um primeiro modelo a um estudo próprio, validado e reprodutível.
- [Tutoriais por área](https://remipelloux.github.io/Modelly/tutorials/domains/index.html): um tutorial por área, cada um construído sobre um modelo do zoo.

## Vindo de outra ferramenta

- [Migrando do Mesa](https://remipelloux.github.io/Modelly/migrating_from_mesa.html): um mapeamento construção a construção e um codemod, `python -m modelly.migrate`, que reescreve as partes mecânicas e relata o restante.
- [Do NetLogo](https://remipelloux.github.io/Modelly/netlogo.html): `python -m modelly.netlogo` traduz um modelo `.nlogo` em um módulo Python que você pode executar, testar e verificar.
- [Do R e do Julia](https://remipelloux.github.io/Modelly/r_and_julia.html): leia os resultados Parquet do Modelly no R e no Julia, e controle um modelo a partir do R.

## Exemplos

O Modelly vem com uma coleção de modelos de exemplo. São ABMs clássicos; se você já conhece ABMs e quer ter uma ideia rápida de como o MODELLY funciona, esses exemplos são um ótimo ponto de partida. Você os encontra [aqui](https://remipelloux.github.io/Modelly/examples.html).

## Mais recursos

Para explorar mais o Modelly e seus recursos, estão disponíveis:

### Documentação da API

- [Referência da API do Modelly](https://remipelloux.github.io/Modelly/apis/api_main.html): documentação detalhada das classes e funções do Modelly, uma página por pacote (`modelly.core`, `modelly.space`, `modelly.time`, `modelly.data`, `modelly.behaviour`, `modelly.scenarios`, `modelly.batch`, `modelly.viz`).

### Código-fonte e desenvolvimento

- [Repositório do Modelly no GitHub](https://github.com/RemiPelloux/Modelly): acesse todo o código-fonte do Modelly, contribua para o seu desenvolvimento ou relate problemas.
- [Notas de versão do Modelly](https://github.com/RemiPelloux/Modelly/releases): veja o registro detalhado de mudanças do Modelly, com todas as versões anteriores e seus recursos.

### Comunidade e suporte

- [GitHub Discussions do Modelly](https://github.com/RemiPelloux/Modelly/discussions): participe das discussões, faça perguntas e converse com outros usuários do Modelly.

Divirta-se modelando com o Modelly, e fique à vontade para entrar em contato!
