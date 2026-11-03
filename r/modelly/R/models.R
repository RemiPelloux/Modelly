# Running models: parameters, one run, the model object itself.

#' The parameters of a model's scenario
#'
#' @param target "path/to/model.py:Class" or "package.module:Class".
#' @return A data frame: name, type and default of each parameter.
#' @export
modelly_parameters <- function(target) {
  plain(bindings()$parameters(target))
}

#' Build a model
#'
#' @param target "path/to/model.py:Class" or "package.module:Class".
#' @param ... Scenario parameters, by name. Whole numbers may be written without L.
#' @param seed The seed of the run.
#' @return The Python model; call its methods with $, for example model$step().
#' @export
modelly_model <- function(target, ..., seed = 0L) {
  bindings()$model(target, list(...), as.integer(seed))
}

#' Run a model and collect its reporters
#'
#' @inheritParams modelly_model
#' @param steps The number of steps.
#' @return A data frame with a step column and one column per model reporter.
#' @export
modelly_run <- function(target, ..., seed = 0L, steps = 100L) {
  plain(bindings()$simulate(target, list(...), as.integer(seed), as.integer(steps)))
}

#' The path of a file of the package's tutorial
#'
#' @param file A file in inst/tutorial, by default the SIR model.
#' @return Its path, to use in a target ("<path>:Epidemic").
#' @export
modelly_tutorial <- function(file = "epidemic.py") {
  system.file("tutorial", file, package = "modelly", mustWork = TRUE)
}
