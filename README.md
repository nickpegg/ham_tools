# ham tools

A collection of little tools I've written to help me with amateur radio stuff.

My motivation for this was originally that CHIRP didn't support the FT-991a, so
I figured that equipped with the CAT manual for it, I could put together a
script easily enough to program memories on this radio via CAT.

* `ft991a` - Tool to read/write channel memory and settings to a FT-991a over the CAT serial protocol
* `cat_shell` - REPL shell for your radio. Type in a CAT command, and it'll print the response
* `rigctl_meters` - Show meters from the radio, read from rigctld - input signal
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


# TODO

## Features
- [x] Read/write memory channels
- [x] Read/write CTCSS tones and DCS codes along with memory
- [x] read/write memory to/from CSV
- [x] Add memory writing to CLI
- [ ] (ft991a) Menu settings read/write - tough because types are so different between settings
- [ ] (rigctl_meters) Make meter value red when over limit


## Refactoring

- [x] Test against various Python versions
- [x] Make radio functions into a class
- [x] Separate CLI code from business logic
- [x] Make CAT shell its own command
