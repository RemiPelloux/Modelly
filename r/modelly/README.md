# modelly (R)

Run, sweep and calibrate [Modelly](https://github.com/RemiPelloux/Modelly) agent-based
models from R. Modelly runs in Python through
[reticulate](https://rstudio.github.io/reticulate/); results come back as data frames.

```r
install.packages("reticulate")
remotes::install_github("RemiPelloux/Modelly", subdir = "r/modelly")
modelly::install_modelly()          # once: a Python environment with modelly-abm

library(modelly)
target <- paste0(modelly_tutorial(), ":Epidemic")   # the SIR model of the tutorial
run <- modelly_run(target, beta = 0.4, seed = 99, steps = 40)
fit <- modelly_calibrate(target,
  priors = list(beta = prior_uniform(0.05, 1), gamma = prior_uniform(0.02, 0.5)),
  observed = list(infected = run$infected[-1]), steps = 40, seed = 2027)
fit
plot(fit)
```

Any model works: `modelly_run("path/to/model.py:MyModel", ...)`. The guide is
[From R and Julia](https://remipelloux.github.io/Modelly/dev/r_and_julia.html).
