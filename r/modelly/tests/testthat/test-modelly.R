skip_if_not(modelly_available(), "Modelly is not installed in reticulate's Python")

target <- paste0(modelly_tutorial(), ":Epidemic")

test_that("the parameters of the tutorial model are listed", {
  params <- modelly_parameters(target)
  expect_s3_class(params, "data.frame")
  expect_equal(params$name, c("beta", "gamma", "population", "initial"))
})

test_that("a run returns a data frame, the same for the same seed", {
  run <- modelly_run(target, beta = 0.4, population = 1000, seed = 99, steps = 40)
  expect_equal(nrow(run), 41)
  expect_equal(run$susceptible + run$infected + run$recovered, rep(1000, 41))
  expect_identical(run, modelly_run(target, beta = 0.4, population = 1000, seed = 99, steps = 40))
})

test_that("a model can be stepped from R", {
  model <- modelly_model(target, seed = 1)
  model$step()
  expect_equal(model$susceptible + model$infected + model$recovered, 1000)
})

test_that("the SIR calibration tutorial recovers beta and gamma", {
  cases <- modelly_run(target, beta = 0.4, gamma = 0.1, seed = 99, steps = 40)$infected[-1]
  fit <- modelly_calibrate(
    target,
    priors = list(beta = prior_uniform(0.05, 1), gamma = prior_uniform(0.02, 0.5)),
    observed = list(infected = cases), steps = 40, particles = 100, generations = 6,
    seed = 2027
  )
  expect_s3_class(fit, "modelly_posterior")
  s <- fit$summary
  expect_true(s$hdi_low[s$parameter == "beta"] < 0.4 && 0.4 < s$hdi_high[s$parameter == "beta"])
  expect_true(s$hdi_low[s$parameter == "gamma"] < 0.1 && 0.1 < s$hdi_high[s$parameter == "gamma"])
  expect_equal(round(s$mean[s$parameter == "beta"], 3), 0.423)
  expect_output(print(fit), "ABC-SMC posterior")
})

test_that("a bad prior is refused", {
  expect_error(modelly_calibrate(target, list(beta = list("cauchy", 0, 1)),
                                 list(infected = 1:40), steps = 40))
})
