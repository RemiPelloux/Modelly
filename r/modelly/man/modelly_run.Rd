\name{modelly_run}
\alias{modelly_run}
\title{Run a model and collect its reporters}
\usage{
modelly_run(target, ..., seed = 0L, steps = 100L)
}
\arguments{
\item{target}{"path/to/model.py:Class" or "package.module:Class".}
\item{...}{Scenario parameters, by name.}
\item{seed}{The seed of the run.}
\item{steps}{The number of steps.}
}
\value{
A data frame with a step column and one column per model reporter.
}
\description{
Run a model and collect its reporters.
}
\examples{
if (modelly_available()) {
  run <- modelly_run(paste0(modelly_tutorial(), ":Epidemic"), seed = 99, steps = 40)
  plot(run$step, run$infected, type = "l")
}
}
