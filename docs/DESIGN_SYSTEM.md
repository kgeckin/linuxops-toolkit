# Visual and information design

LinuxOps uses the same restrained brand language as StorageOps Lab: blue-black surfaces, champagne capacity emphasis, blue performance signals and teal healthy or live data. Light and dark themes are supported because no one palette is uniquely ideal for every user or every viewing environment.

Colors are paired with textual values and severity labels so meaning is not only carried by hue. The interface uses readable font sizing, keyboard focus styles, explicit navigation state, and `prefers-reduced-motion` to remove transitions.

Scientific and accessibility foundations:

* [W3C WCAG 2.2](https://www.w3.org/TR/WCAG22/): minimum 4.5:1 contrast for ordinary text, 3:1 for large text and meaningful non-text elements.
* [IBM Carbon color](https://carbondesignsystem.com/elements/color/overview/): neutral surface hierarchies and purposeful semantic colors.

Design decisions have not undergone complete cross-browser, color-vision or usability testing. WCAG compliance should not be claimed for the entire interface based only on the palette.

## Information hierarchy

1. Overview: current CPU, RAM, disk, uptime, recent history, health and cumulative network totals.
2. Compute: resource trends and explicitly distinct kernel load average.
3. Storage: capacity at a chosen mount with optional history.
4. Network: derivative throughput values with a counters-reset caveat.
5. Alerts: transparent thresholds, never invented anomalies.
6. How it works: architecture, CLI and privacy boundary.

## Data trust

Every numerical value shown in the dashboard is obtained from the local `/api/v1/overview` or `/api/v1/history` endpoint. Empty charts indicate no timeline yet. No chart synthesizes a false moving series or fake production hardware sample.
