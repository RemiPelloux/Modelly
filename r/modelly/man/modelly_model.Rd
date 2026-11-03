\name{modelly_model}
\alias{modelly_model}
\title{Build a model}
\usage{
modelly_model(target, ..., seed = 0L)
}
\arguments{
\item{target}{"path/to/model.py:Class" or "package.module:Class".}
\item{...}{Scenario parameters, by name. Whole numbers may be written without L.}
\item{seed}{The seed of the run.}
}
\value{
The Python model; call its methods with $, for example model$step().
}
\description{
Build a model.
}
\examples{
if (modelly_available()) {
  model <- modelly_model(paste0(modelly_tutorial(), ":Epidemic"), beta = 0.3)
  model$step()
}
}
