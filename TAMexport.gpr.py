# File: TAMexport.gpr.py
register(REPORT,
  id    = 'TAMexport',
  name  = _("TAM exporter"),
  description =  _("JSON-export for use with TAM."),
  version = '1.0',
  gramps_target_version = '5.1',
  status = STABLE,
  fname = 'tamexport.py',
  authors = ["IOhannes m zmölnig"],
  authors_email = ["zmoelnig@umlaeute.mur.at"],
  category = CATEGORY_GRAPHVIZ,
  require_active = False,
  reportclass = 'TAMexportReport',
  optionclass = 'TAMexportOptions',
  report_modes = [REPORT_MODE_GUI, REPORT_MODE_CLI],
)


