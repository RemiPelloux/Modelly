\name{print.modelly_posterior}
\alias{print.modelly_posterior}
\alias{plot.modelly_posterior}
\title{Print and plot a calibration's posterior}
\usage{
\method{print}{modelly_posterior}(x, ...)

\method{plot}{modelly_posterior}(x, ...)
}
\arguments{
\item{x}{A modelly_posterior from modelly_calibrate().}
\item{...}{Passed to hist() by plot().}
}
\value{
\code{x}, invisibly.
}
\description{
The summary of each parameter, or a histogram of its particles.
}
