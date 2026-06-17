ZCBS Solar Simulator (LEDSS) — Session Logger
==============================================

REQUIREMENTS
  Python 3.7+ — https://www.python.org
  During installation, tick "Add Python to PATH".
  No extra packages needed.

ASSETS (place in this folder)
  Nord.ttf             custom font
  SUN_SQUARE.png       logo shown below the title

LAUNCH (choose one)
  launch.vbs   — double-click, opens app with NO terminal window (recommended)
  run.bat      — also silent (uses pythonw, no console)

DATA FILES  (keep these — do not edit manually)
  sun_log.csv         session log
  sun_log.csv.bak     auto-backup before every save
  sun_stats.json      accumulated hours + session count
  sun_state.json      active session (removed on clean end)

EXPORT
  Click "Export CSV" in the app footer.

CSV COLUMNS
  ID, Date, Start Time, End Time, Duration (h),
  Researcher, Lab Member, Operation, Experiment,
  Max Azimuth (deg), Min Azimuth (deg),
  Max Altitude (deg), Min Altitude (deg),
  WW Power (%), CW Power (%), IR Power (%),
  Remarks, Maintenance Required
