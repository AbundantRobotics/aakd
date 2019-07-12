# AbundantRobotics AKD library and tools `aakd`

Python tools for Kollmorgen AKD drives

# Installation

This is a fully fledged python3 package that you can install with pip (`pip3 install git+https://github.com/abundantrobotics/aakd`) or any usual way.

# Completion
Completion of the `aakd` script is provided by `argcomplete`. But depending on the installation (esp through `pip`), completion handlers are not installed by default.

To force the completion handler to exist, you can simply run:
```bash
eval $(register-python-argcomplete aakd)
```
