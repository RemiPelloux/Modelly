# Primeros pasos
*Esta página es una traducción de la [página en inglés](../../getting_started.md); las correcciones son bienvenidas.*

Modelly es un framework modular para construir, analizar y visualizar modelos basados en agentes.

Los **modelos basados en agentes** son simulaciones por ordenador en las que varias entidades (los agentes) actúan e interactúan entre sí según el comportamiento que se les ha programado. Los agentes pueden representar células vivas, animales, personas, e incluso organizaciones enteras o entidades abstractas. A veces entendemos cómo se comportan los componentes individuales de un sistema y queremos ver qué comportamientos y efectos surgen, a nivel del sistema, de su interacción. Otras veces tenemos una buena idea de cómo se comporta el sistema en su conjunto y queremos averiguar qué comportamientos individuales lo explican. O queremos ver cómo conseguir que los agentes cooperen o compitan de la forma más eficaz. O simplemente queremos construir un juguete vistoso con puntitos de colores que se mueven.

## Visión general
Si quiere hacerse una idea general de las funcionalidades y la estructura de Modelly, empiece aquí:

- [Visión general de la biblioteca MODELLY](../../overview): conozca los conceptos y componentes fundamentales de Modelly.

## Tutoriales
Si quiere aprender paso a paso a construir modelos basados en agentes con Modelly, siga estos tutoriales:

- [Crear su primer modelo](../../tutorials/0_first_model): aprenda a crear su primer modelo de Modelly.
- [AgentSet](../../tutorials/1_agentset): aprenda a gestionar los agentes de forma más eficaz con el AgentSet de Modelly.
- [Activación de agentes](../../tutorials/2_agent_activation): aprenda distintas formas de activar agentes con `do`, `shuffle_do` y `map`, que cubren los patrones de activación aleatoria, secuencial, simultánea, por etapas, por tipo y condicional.
- [Programación de eventos](../../tutorials/3_event_scheduling): aprenda a programar eventos y a gestionar el tiempo en su modelo de Modelly.
- [Añadir un espacio](../../tutorials/4_adding_space): aprenda a añadir un espacio a su modelo de Modelly y a entender la arquitectura de espacios de Modelly.
- [Recoger datos](../../tutorials/5_collecting_data): aprenda a recoger datos a nivel del modelo y de los agentes con el DataCollector de Modelly.
- [Visualización básica](../../tutorials/6_visualization_basic): aprenda a construir un panel interactivo con el módulo de visualización de Modelly.
- [Visualización dinámica de agentes](../../tutorials/7_visualization_dynamic_agents): aprenda a representar dinámicamente sus agentes en su panel interactivo.
- [Visualización con SpaceRenderer](../../tutorials/8_visualization_rendering_with_space_renderer): aprenda a sacar todo el partido de SpaceRenderer para mejorar sus visualizaciones.
- [Visualización de capas de propiedades](../../tutorials/9_visualization_property_layer_visualization): aprenda a visualizar capas de propiedades en Modelly.
- [Componentes de visualización personalizados](../../tutorials/10_visualization_custom): aprenda a añadir componentes visuales personalizados a su panel interactivo.
- [Simulación de eventos discretos](../../tutorials/11_discrete_event_simulation): aprenda a construir un modelo puramente orientado a eventos con `schedule_event` y a validarlo con la teoría de colas.
- [Modelos híbridos ABM-DEVS](../../tutorials/12_hybrid_abm_devs): aprenda a combinar la activación de agentes basada en `step()` con eventos programados en un modelo epidémico espacial.

## Su propio proyecto
- [Usar Modelly en su proyecto](../../using_modelly_in_your_project): de una carpeta vacía a un modelo reproducible y medido que vive en su propio repositorio.
- [Empezar un proyecto](../../new_project): `modelly new` escribe un proyecto con semilla, pruebas y verificación desde su primer commit.
- [Buenas prácticas de Modelly](../../best-practices): un resumen de consejos y pautas para usar Modelly.

## Cursos y tutoriales por dominio
- [Curso](../../course/index): doce sesiones que llevan a una clase desde un primer modelo hasta un estudio propio, validado y reproducible.
- [Tutoriales por dominio](../../tutorials/domains/index): un tutorial por disciplina, cada uno construido sobre un modelo del zoo.

## Si viene de otra herramienta
- [Migrar desde Mesa](../../migrating_from_mesa): una correspondencia construcción por construcción y un codemod, `python -m modelly.migrate`, que reescribe las partes mecánicas e informa del resto.
- [Desde NetLogo](../../netlogo): `python -m modelly.netlogo` traduce un modelo `.nlogo` a un módulo de Python que puede ejecutar, probar y verificar.
- [Desde R y Julia](../../r_and_julia): lea los resultados Parquet de Modelly desde R y Julia, y controle un modelo desde R.

## Ejemplos
Modelly incluye una colección de modelos de ejemplo. Son ABM clásicos, así que si ya conoce los ABM y quiere hacerse una idea rápida de cómo funciona MODELLY, estos ejemplos son un excelente punto de partida. Los encontrará [aquí](../../examples).

## Más recursos
Para seguir explorando Modelly y sus funcionalidades, tiene a su disposición los siguientes recursos:

### Documentación de la API
- [Referencia de la API de Modelly](../../apis/api_main.md): documentación detallada de las clases y funciones de Modelly, una página por paquete (`modelly.core`, `modelly.space`, `modelly.time`, `modelly.data`, `modelly.behaviour`, `modelly.scenarios`, `modelly.batch`, `modelly.viz`).

### Código fuente y desarrollo
- [Repositorio de Modelly en GitHub](https://github.com/RemiPelloux/Modelly): acceda a todo el código fuente de Modelly, contribuya a su desarrollo o informe de problemas.
- [Notas de versión de Modelly](https://github.com/RemiPelloux/Modelly/releases): consulte el registro de cambios detallado de Modelly, con todas las versiones anteriores y sus funcionalidades.

### Comunidad y soporte
- [GitHub Discussions de Modelly](https://github.com/RemiPelloux/Modelly/discussions): únase a las conversaciones, haga preguntas y conecte con otros usuarios de Modelly.

¡Disfrute modelando con Modelly, y no dude en ponerse en contacto!
