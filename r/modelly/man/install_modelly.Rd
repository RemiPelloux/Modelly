\name{install_modelly}
\alias{install_modelly}
\title{Install Modelly in a Python environment for reticulate}
\usage{
install_modelly(envname = "r-modelly", version = NULL, ...)
}
\arguments{
\item{envname}{The virtual environment to install into.}
\item{version}{A Modelly version, such as "1.5.0", or NULL for the latest.}
\item{...}{Passed to reticulate::py_install().}
}
\value{
Invisibly, what reticulate::py_install() returns.
}
\description{
Install Modelly in a Python environment for reticulate.
}
\examples{
\dontrun{
install_modelly()
}
}
