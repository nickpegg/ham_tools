# ham tools

A collection of little tools I've written to help me with amateur radio stuff.

My motivation for this was originally that CHIRP didn't support the FT-991a, so
I figured that equipped with the CAT manual for it, I could put together a
script easily enough to program memories on this radio via CAT.

* `ft991a` - Tool to read/write channel memory and settings to a FT-991a over the CAT serial protocol


# TODO

## Features
- [x] Read/write memory channels
- [x] Read/write CTCSS tones and DCS codes along with memory
- [ ] Menu settings read/write


## Refactoring

- [x] Test against various Python versions
- [x] Make radio functions into a class
- [ ] Separate CLI code from business logic
- [ ] Make CAT shell its own command
