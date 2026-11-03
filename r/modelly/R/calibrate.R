# Calibration by ABC-SMC, and the priors it takes.

#' Priors for modelly_calibrate()
#'
#' @param low,high The bounds of a uniform or log-uniform prior.
#' @param mean,sd The mean and standard deviation of a normal prior.
#' @param mu,sigma The parameters of a log-normal prior (of the logarithm).
#' @return A prior, as modelly_calibrate() takes it.
#' @name priors
NULL

#' @rdname priors
#' @export
prior_uniform <- function(low, high) list("uniform", low, high)

#' @rdname priors
#' @export
prior_log_uniform <- function(low, high) list("log_uniform", low, high)

#' @rdname priors
#' @export
prior_normal <- function(mean, sd) list("normal", mean, sd)

#' @rdname priors
#' @export
prior_log_normal <- function(mu, sigma) list("log_normal", mu, sigma)

#' Calibrate a model to observed series by ABC-SMC
#'
#' @param target "path/to/model.py:Class" or "package.module:Class".
#' @param priors A named list of priors, one per fitted parameter.
#' @param observed A named list: a model reporter and its observed values, one per step.
#' @param steps The number of steps of each run.
#' @param particles The number of particles.
#' @param generations The number of generations.
#' @param seed The seed of the calibration; the same seed gives the same posterior.
#' @param fixed A named list of parameters every run takes.
#' @return A modelly_posterior: summary, particles and trace data frames.
#' @export
modelly_calibrate <- function(target, priors, observed, steps, particles = 100L,
                              generations = 6L, seed = 0L, fixed = list()) {
  result <- bindings()$calibrate(
    target, priors, observed,
    steps = as.integer(steps), particles = as.integer(particles),
    generations = as.integer(generations), seed = as.integer(seed), fixed = fixed
  )
  structure(lapply(result, plain), class = "modelly_posterior")
}

#' @export
print.modelly_posterior <- function(x, ...) {
  cat("ABC-SMC posterior,", nrow(x$particles), "particles\n")
  print(x$summary, row.names = FALSE)
  invisible(x)
}

#' @export
plot.modelly_posterior <- function(x, ...) {
  names <- x$summary$parameter
  old <- par(mfrow = c(1, length(names)))
  on.exit(par(old))
  for (name in names) {
    hist(x$particles[[name]], main = name, xlab = name, ...)
  }
  invisible(x)
}
