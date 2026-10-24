# Wolf-Sheep Predation Model

## Summary

A simple ecological model, consisting of three agent types: wolves, sheep, and grass. The wolves and the sheep wander around the grid at random. Wolves and sheep both expend energy moving around, and replenish it by eating. Sheep eat grass, and wolves eat sheep if they end up on the same grid cell.

If wolves and sheep have enough energy, they reproduce, creating a new wolf or sheep (in this simplified model, only one parent is needed for reproduction). The grass on each cell regrows at a constant rate. If any wolves and sheep run out of energy, they die.

The model is tests and demonstrates several Modelly concepts and features:
 - OrthogonalVonNeumannGrid
 - Multiple agent types (wolves, sheep, grass)
 - Agents inheriting a behavior (random movement) from an abstract parent
 - Writing a model composed of multiple files.
 - Dynamically adding and removing agents from the model

## How to Run

Install Modelly with recommended dependencies:

pip install "modelly-abm[rec]"

Then run the example:

solara run app.py

Open the displayed local URL in your browser.

## Files

* ``agents.py``: Defines the ``Animal`` base class, which moves randomly across the grid one cell at a time, and the Wolf, Sheep and GrassPatch agent classes.
* ``model.py``: Defines the Wolf-Sheep Predation model itself and its scenario.
* ``app.py``: Sets up the interactive Solara visualization.

## Further Reading

This model is closely based on the NetLogo Wolf-Sheep Predation Model:

Wilensky, U. (1997). NetLogo Wolf Sheep Predation model. http://ccl.northwestern.edu/netlogo/models/WolfSheepPredation. Center for Connected Learning and Computer-Based Modeling, Northwestern University, Evanston, IL.

See also the [Lotka–Volterra equations
](https://en.wikipedia.org/wiki/Lotka%E2%80%93Volterra_equations) for an example of a classic differential-equation model with similar dynamics.
