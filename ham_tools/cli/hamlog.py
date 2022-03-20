"""
CLI tool for managing an ADIF log collection

Log files are stored in:
~/Documents/amateur_radio/log/<log name>/<year>/<month>/YYYY-MM-DD.adi
"""

# TODO: Subcommands:
# - import <filename> - merge the file into the log
# - query <query> - Use a JMESPath query to query the log
# - export <filename> [query] - Export the log to a file, optionally filtering by a
#                               JMESPath query
