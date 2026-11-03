\name{modelly_calibrate}
\alias{modelly_calibrate}
\title{Calibrate a model to observed series by ABC-SMC}
\usage{
modelly_calibrate(target, priors, observed, steps, particles = 100L,
  generations = 6L, seed = 0L, fixed = list())
}
\arguments{
\item{target}{"path/to/model.py:Class" or "package.module:Class".}
\item{priors}{A named list of priors, one per fitted parameter (see \code{\link{prior_uniform}}).}
\item{observed}{A named list: a model reporter and its observed values, one per step.}
\item{steps}{The number of steps of each run.}
\item{particles}{The number of particles.}
\item{generations}{The number of generations.}
\item{seed}{The seed of the calibration; the same seed gives the same posterior.}
\item{fixed}{A named list of parameters every run takes.}
}
\value{
A modelly_posterior: a list of summary, particles and trace data frames, with print and plot methods.
}
\description{
Calibrate a model to observed series by ABC-SMC.
}
\examples{
if (modelly_available()) {
  target <- paste0(modelly_tutorial(), ":Epidemic")
  cases <- modelly_run(target, seed = 99, steps = 40)$infected[-1]
  fit <- modelly_calibrate(target,
    priors = list(beta = prior_uniform(0.05, 1), gamma = prior_uniform(0.02, 0.5)),
    observed = list(infected = cases), steps = 40, particles = 50, generations = 3,
    seed = 2027)
  fit
}
}
