# Premiers pas

*Cette page est une traduction de la [page anglaise](https://remipelloux.github.io/Modelly/getting_started.html) ; les corrections sont les bienvenues.*

Modelly est un framework modulaire pour construire, analyser et visualiser des modèles à base d’agents.

Les **modèles à base d’agents** sont des simulations informatiques où plusieurs entités (les agents) agissent et interagissent les unes avec les autres selon le comportement qui leur a été programmé. Les agents peuvent représenter des cellules vivantes, des animaux, des êtres humains, voire des organisations entières ou des entités abstraites. Parfois, on comprend comment se comportent les composants individuels d’un système et l’on veut voir quels comportements et quels effets émergent, à l’échelle du système, de leurs interactions. D’autres fois, on a une bonne idée du comportement global du système et l’on cherche quels comportements individuels l’expliquent. Ou bien on veut savoir comment amener des agents à coopérer ou à se concurrencer le plus efficacement possible. Ou l’on veut simplement construire un joli jouet avec de petits points colorés qui se déplacent.

## Vue d’ensemble

Pour avoir une idée générale des fonctionnalités et de la structure de Modelly, commencez ici :

- [Vue d’ensemble de la bibliothèque MODELLY](https://remipelloux.github.io/Modelly/overview.html) : découvrez les concepts et composants essentiels de Modelly.

## Tutoriels

Pour apprendre pas à pas à construire des modèles à base d’agents avec Modelly, suivez ces tutoriels :

- [Créer votre premier modèle](https://remipelloux.github.io/Modelly/tutorials/0_first_model.html) : apprenez à créer votre premier modèle Modelly.
- [AgentSet](https://remipelloux.github.io/Modelly/tutorials/1_agentset.html) : apprenez à gérer plus efficacement les agents avec l’AgentSet de Modelly.
- [Activation des agents](https://remipelloux.github.io/Modelly/tutorials/2_agent_activation.html) : découvrez différentes façons d’activer les agents avec `do`, `shuffle_do` et `map`, qui couvrent les activations aléatoire, séquentielle, simultanée, par étapes, par type et conditionnelle.
- [Planification d’événements](https://remipelloux.github.io/Modelly/tutorials/3_event_scheduling.html) : apprenez à planifier des événements et à gérer le temps dans votre modèle Modelly.
- [Ajouter un espace](https://remipelloux.github.io/Modelly/tutorials/4_adding_space.html) : apprenez à ajouter un espace à votre modèle Modelly et à comprendre l’architecture des espaces de Modelly.
- [Collecter des données](https://remipelloux.github.io/Modelly/tutorials/5_collecting_data.html) : apprenez à collecter des données au niveau du modèle et des agents avec le DataCollector de Modelly.
- [Visualisation de base](https://remipelloux.github.io/Modelly/tutorials/6_visualization_basic.html) : apprenez à construire un tableau de bord interactif avec le module de visualisation de Modelly.
- [Visualisation dynamique des agents](https://remipelloux.github.io/Modelly/tutorials/7_visualization_dynamic_agents.html) : apprenez à représenter dynamiquement vos agents dans votre tableau de bord interactif.
- [Visualisation avec SpaceRenderer](https://remipelloux.github.io/Modelly/tutorials/8_visualization_rendering_with_space_renderer.html) : apprenez à tirer pleinement parti de SpaceRenderer pour enrichir vos visualisations.
- [Visualisation des couches de propriétés](https://remipelloux.github.io/Modelly/tutorials/9_visualization_property_layer_visualization.html) : apprenez à visualiser les couches de propriétés dans Modelly.
- [Composants de visualisation personnalisés](https://remipelloux.github.io/Modelly/tutorials/10_visualization_custom.html) : apprenez à ajouter des composants visuels personnalisés à votre tableau de bord interactif.
- [Simulation à événements discrets](https://remipelloux.github.io/Modelly/tutorials/11_discrete_event_simulation.html) : apprenez à construire un modèle purement événementiel avec `schedule_event` et à le valider par la théorie des files d’attente.
- [Modèles hybrides ABM-DEVS](https://remipelloux.github.io/Modelly/tutorials/12_hybrid_abm_devs.html) : apprenez à combiner l’activation des agents par `step()` et des événements planifiés dans un modèle épidémique spatial.

## Votre propre projet

- [Utiliser Modelly dans votre projet](https://remipelloux.github.io/Modelly/using_modelly_in_your_project.html) : d’un dossier vide à un modèle reproductible et mesuré, dans son propre dépôt.
- [Démarrer un projet](https://remipelloux.github.io/Modelly/new_project.html) : `modelly new` écrit un projet initialisé avec une graine, testé et vérifié dès son premier commit.
- [Bonnes pratiques Modelly](https://remipelloux.github.io/Modelly/best-practices.html) : un tour d’horizon des conseils et des recommandations pour utiliser Modelly.

## Cours et tutoriels par domaine

- [Cours](https://remipelloux.github.io/Modelly/course/index.html) : douze séances qui mènent une classe d’un premier modèle à une étude validée et reproductible qui lui est propre.
- [Tutoriels par domaine](https://remipelloux.github.io/Modelly/tutorials/domains/index.html) : un tutoriel par discipline, chacun construit sur un modèle du zoo.

## Venir d’un autre outil

- [Migrer depuis Mesa](https://remipelloux.github.io/Modelly/migrating_from_mesa.html) : une correspondance construction par construction et un codemod, `python -m modelly.migrate`, qui réécrit les parties mécaniques et signale le reste.
- [Depuis NetLogo](https://remipelloux.github.io/Modelly/netlogo.html) : `python -m modelly.netlogo` traduit un modèle `.nlogo` en un module Python que vous pouvez exécuter, tester et vérifier.
- [Depuis R et Julia](https://remipelloux.github.io/Modelly/r_and_julia.html) : lisez les résultats Parquet de Modelly depuis R et Julia, et pilotez un modèle depuis R.

## Exemples

Modelly est livré avec une collection de modèles d’exemple. Ce sont des ABM classiques : si vous connaissez déjà les ABM et voulez vous faire rapidement une idée du fonctionnement de MODELLY, ces exemples sont un excellent point de départ. Vous les trouverez [ici](https://remipelloux.github.io/Modelly/examples.html).

## Ressources complémentaires

Pour explorer davantage Modelly et ses fonctionnalités, les ressources suivantes sont disponibles :

### Documentation de l’API

- [Référence de l’API Modelly](https://remipelloux.github.io/Modelly/apis/api_main.html) : documentation détaillée des classes et fonctions de Modelly, une page par paquet (`modelly.core`, `modelly.space`, `modelly.time`, `modelly.data`, `modelly.behaviour`, `modelly.scenarios`, `modelly.batch`, `modelly.viz`).

### Code source et développement

- [Dépôt GitHub de Modelly](https://github.com/RemiPelloux/Modelly) : accédez à tout le code source de Modelly, contribuez à son développement ou signalez des problèmes.
- [Notes de version de Modelly](https://github.com/RemiPelloux/Modelly/releases) : consultez le journal des modifications détaillé de Modelly, avec toutes les versions passées et leurs fonctionnalités.

### Communauté et assistance

- [Discussions GitHub de Modelly](https://github.com/RemiPelloux/Modelly/discussions) : participez aux discussions, posez vos questions et échangez avec d’autres utilisateurs de Modelly.

Bonne modélisation avec Modelly, et n’hésitez pas à nous contacter !
