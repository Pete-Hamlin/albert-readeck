# Albert Readeck

A python plugin to allow [albert](https://github.com/albertlauncher/albert) to interact with a [readeck](https://codeberg.org/readeck/readeck) instance.
Based off [albert-linkding](https://github.com/sissbruecker/linkding).
Currently supports the following features

- Trigger query search of links (default `rd`) by URL/name/labels
- Global query results from vault notes via URL/name/labels
- Queries support the following actions:
  - Opening bookmark in readeck
  - Opening original bookmark URL in browser
  - Copying link URL
  - Archiving bookmark
  - Deleting bookmark
- An indexer that re-indexes on a configurable interval (default: `15` minutes)
- Some [basic settings](#settings) to customise behaviour

## Install

Run the follow from a terminal:

```shell
git clone https://github.com/Pete-Hamlin/albert-readeck.git $HOME/.local/share/albert/python/plugins/readeck
```

Then enable the plugin from the albert settings panel (you **must** enable the python plugin for this plugin to be visible/loadable)

## Settings

| Setting        | Description                                                                                                             | Default                         |
| -------------- | ----------------------------------------------------------------------------------------------------------------------- | ------------------------------- |
| `instance_url` | URL where your readeck instance is hosted                                                                               | default `http://localhost:8000` |
| `api_key`      | A valid API token for the readeck API. You will need to generate an API key in your settings page to use this extension | default `None`                  |
| `cache_length` | The length of time to wait between refreshing the index of links (in minutes).                                          | default `15`                    |
