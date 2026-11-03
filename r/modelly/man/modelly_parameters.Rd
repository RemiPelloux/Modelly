\name{modelly_parameters}
\alias{modelly_parameters}
\title{The parameters of a model's scenario}
\usage{
modelly_parameters(target)
}
\arguments{
\item{target}{"path/to/model.py:Class" or "package.module:Class".}
}
\value{
A data frame: name, type and default of each parameter.
}
\description{
The parameters of a model's scenario.
}
\examples{
if (modelly_available()) {
  modelly_parameters(paste0(modelly_tutorial(), ":Epidemic"))
}
}
