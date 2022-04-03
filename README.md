# ham tools

A collection of little tools I've written to help me with amateur radio stuff.

My motivation for this was originally that CHIRP didn't support the FT-991a, so
I figured that equipped with the CAT manual for it, I could put together a
script easily enough to program memories on this radio via CAT.

* `ft991a` - Tool to read/write channel memory and settings to a FT-991a over the CAT serial protocol
* `cat_shell` - REPL shell for your radio. Type in a CAT command, and it'll print the response
* `rig_meters` - Show meters from the radio, read from rigctld - input signal
  strength, ALC, SWR, and output RF power. Saves you from having to flip between the
various meters on the radio.

# Installation
```
pip install git+https://github.com/nickpegg/ham_tools.git
```

# Example usage

First, dump your radio's existing memories to a CSV file:
```
ft991a read memory
```

Then, edit the CSV file it wrote the memories to, adding stations or making changes.

Now, write the memories from the CSV back to the radio:
```
ft991a write memory
```


# Development

After cloning the repo, run `make init` to install all of the dependencies.

The CLI tools are all defined in the `[tool.poetry.scripts]` section in the
`pyproject.toml` file. You can run each one with `poetry run`, for example:
`poetry run ft991a -h`.

`make fmt` will run code formatters, `make test` will run the standard suite of
tests. Just running `make` will run both of these.

There are some integration tests which require a real Yaesu FT-991a to be
plugged in via USB, these can be ran with `run integration`. You should make
sure that other programs aren't trying to use the radio at the same time, like
you should stop rigctl, WSJT-X, etc.


# TODO

## Features
- [x] Read/write memory channels
- [x] Read/write CTCSS tones and DCS codes along with memory
- [x] read/write memory to/from CSV
- [x] Add memory writing to CLI
- [ ] `ft991a` - Menu settings read/write - tough because types are so different between settings
- [x] `rig_meters` - Make meter value red when over limit

## Log Manager
- [x] ADIF parser/merger
- [ ] CLI tool to merge ADIFs and manage a central log
- [ ] simple web UI for manual logging
- [ ] Push logs to LOTW
- [ ] Push logs to ClubLog
- [ ] Push logs to eQSL
