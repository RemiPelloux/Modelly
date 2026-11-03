# The Python side: modelly.bindings, imported once on first use.
.modelly <- new.env(parent = emptyenv())

bindings <- function() {
  if (is.null(.modelly$py)) {
    if (!reticulate::py_module_available("modelly")) {
      stop("Modelly is not installed in reticulate's Python: run install_modelly()",
           call. = FALSE)
    }
    .modelly$py <- reticulate::import("modelly.bindings")
  }
  .modelly$py
}

#' Install Modelly in a Python environment for reticulate
#'
#' @param envname The virtual environment to install into.
#' @param version A Modelly version, such as "1.5.0", or NULL for the latest.
#' @param ... Passed to reticulate::py_install().
#' @return Invisibly, what reticulate::py_install() returns.
#' @export
install_modelly <- function(envname = "r-modelly", version = NULL, ...) {
  package <- if (is.null(version)) "modelly-abm" else paste0("modelly-abm==", version)
  invisible(reticulate::py_install(package, envname = envname, pip = TRUE, ...))
}

#' Whether Modelly can be imported from R
#'
#' @return TRUE when reticulate's Python has the modelly package.
#' @export
modelly_available <- function() {
  reticulate::py_module_available("modelly")
}

# A pandas DataFrame from reticulate as a plain R data frame, without the index pointer.
plain <- function(frame) {
  attr(frame, "pandas.index") <- NULL
  frame
}
