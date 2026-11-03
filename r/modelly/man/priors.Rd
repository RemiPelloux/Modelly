\name{priors}
\alias{priors}
\alias{prior_uniform}
\alias{prior_log_uniform}
\alias{prior_normal}
\alias{prior_log_normal}
\title{Priors for modelly_calibrate()}
\usage{
prior_uniform(low, high)

prior_log_uniform(low, high)

prior_normal(mean, sd)

prior_log_normal(mu, sigma)
}
\arguments{
\item{low, high}{The bounds of a uniform or log-uniform prior.}
\item{mean, sd}{The mean and standard deviation of a normal prior.}
\item{mu, sigma}{The parameters of a log-normal prior (of the logarithm).}
}
\value{
A prior, as modelly_calibrate() takes it.
}
\description{
Priors for modelly_calibrate().
}
\examples{
prior_uniform(0.05, 1)
}
