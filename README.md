# ansiconv

Convert terminal output between ANSI SGR escape sequences and HTML.

Build logs, CI output, and command captures usually come out of the
terminal full of colour and style codes (`\x1b[1;31m`, `\x1b[0m`, and so
on). Dropping that raw text into a web page just shows the escape bytes
as garbage, and stripping them loses the colour information you probably
wanted to keep. `ansiconv` converts one direction to `<span>`-based HTML
and back, so a terminal recording can go through a browser and come back
out looking the same.

It only understands "standard" SGR codes: reset, bold/italic/underline
on and off, and the 16 named foreground/background colours (including
bright variants). 256-colour and truecolor codes aren't modeled yet
(see Roadmap in the repo).

## Strict vs. lenient

By default the converter is strict: any escape sequence or HTML tag it
doesn't recognize raises an error and stops the conversion. That's the
right default because a silently-mangled log is worse than a loud
failure — you want to know your input had something you didn't expect.

Pass `--lenient` to instead skip anything unrecognized and keep going.
Reach for it when you're converting output you don't control, such as a
log file with cursor-movement or 256-colour codes mixed in, and you'd
rather lose that formatting than lose the whole run.

## Usage

```
$ python3 -c "print('\x1b[1;31mERROR\x1b[0m: build failed')" | python -m ansiconv.cli to-html
<span class="ansi-bold ansi-fg-red">ERROR</span>: build failed
```

Round trip back to ANSI:

```
$ echo '<span class="ansi-bold ansi-fg-red">ERROR</span>: build failed' \
    | python -m ansiconv.cli to-ansi
```

Working with files and unsupported input:

```
$ python -m ansiconv.cli to-html build.log -o build.html      # strict: stops on the first oddity
$ python -m ansiconv.cli to-html build.log -o build.html --lenient   # best effort
```

As a library:

```python
from ansiconv import ansi_to_html, html_to_ansi, ConversionError

html = ansi_to_html("\x1b[32mok\x1b[0m")
try:
    ansi_to_html("\x1b[38;5;208mtruecolor\x1b[0m")
except ConversionError:
    ...  # 256-colour codes aren't supported in strict mode yet
```

## Status

Early skeleton. The core SGR <-> HTML mapping works and is covered by
the strict/lenient split described above; see the roadmap for what's
still missing.
