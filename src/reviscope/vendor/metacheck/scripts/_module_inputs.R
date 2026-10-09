# Adapter preconditions only; extraction and numerical checks remain package logic.
mc_missing_module_input <- function(module, paper, extract = metacheck::extract_eq) {
  if (!identical(module, "stat_effect_size")) return(NULL)
  eq <- tryCatch(extract(paper), error = function(e) NULL)
  # An unknown extraction result or parser failure must still reach the package
  # and its ordinary failed-module record; neither establishes inapplicability.
  if (!is.data.frame(eq) || nrow(eq) == 0 || !"lhs" %in% names(eq) ||
      !is.character(eq$lhs) || anyNA(eq$lhs)) return(NULL)
  if (!any(eq$lhs %in% c("t", "F"))) {
    return(paste("The package extracted equations but no t/F candidates.",
                 "Effect-size coherence was not checked; extraction can miss tests."))
  }
  NULL
}
