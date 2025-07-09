import json
from datetime import datetime
from pathlib import Path
from threading import Event, Thread
from time import perf_counter_ns
from urllib import parse

import requests
from albert import *

md_iid = "3.0"
md_version = "0.1.0"
md_name = "Readeck"
md_description = "Manage saved bookmarks via a readeck instance"
md_license = "MIT"
md_url = "https://github.com/Pete-Hamlin/albert-readeck"
md_authors = ["@Pete-Hamlin"]
md_lib_dependencies = ["requests"]


class LinkFetcherThread(Thread):
    def __init__(self, callback, cache_length, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.__stop_event = Event()
        self.__callback = callback
        self.__cache_length = cache_length * 60

    def run(self):
        self.__callback()
        while True:
            self.__stop_event.wait(self.__cache_length)
            if self.__stop_event.is_set():
                return
            self.__callback()

    def stop(self):
        self.__stop_event.set()


class Plugin(PluginInstance, IndexQueryHandler):
    iconUrls = [f"file:{Path(__file__).parent}/readeck.svg"]
    limit = 100
    user_agent = "org.albert.linkding"

    def __init__(self):
        PluginInstance.__init__(self)
        IndexQueryHandler.__init__(self)

        self._index_items = []

        self._instance_url = self.readConfig("instance_url", str) or "http://localhost:8000"
        self._api_key = self.readConfig("api_key", str) or ""
        self._cache_length = self.readConfig("cache_length", int) or 15

        self._thread = LinkFetcherThread(callback=self.fetchIndexItems, cache_length=self._cache_length)
        self._thread.start()

    def __del__(self):
        self._thread.stop()
        self._thread.join()

    def defaultTrigger(self):
        return "rd "

    @property
    def instance_url(self):
        return self._instance_url

    @instance_url.setter
    def instance_url(self, value):
        self._instance_url = value
        self.writeConfig("instance_url", value)

    @property
    def api_key(self):
        return self._api_key

    @api_key.setter
    def api_key(self, value):
        self._api_key = value
        self.writeConfig("api_key", value)

    @property
    def cache_length(self):
        return self._cache_length

    @cache_length.setter
    def cache_length(self, value):
        value = 1 if value < 1 else value
        self._cache_length = value
        self.cache_timeout = datetime.now()
        self.writeConfig("cache_length", value)

        if self._thread.is_alive():
            self._thread.stop()
            self._thread.join()
        self._thread = LinkFetcherThread(callback=self.fetchIndexItems, cache_length=self._cache_length)
        self._thread.start()

    def configWidget(self):
        return [
            {"type": "lineedit", "property": "instance_url", "label": "URL"},
            {
                "type": "lineedit",
                "property": "api_key",
                "label": "API key",
                "widget_properties": {"echoMode": "Password"},
            },
            {"type": "spinbox", "property": "cache_length", "label": "Cache length (minutes)"},
        ]

    def updateIndexItems(self):
        self.setIndexItems(self._index_items)

    def fetchIndexItems(self):
        start = perf_counter_ns()
        data = self._fetch_results()
        for link in data:
            filter = self._create_filters(link)
            item = self._gen_item(link)
            self._index_items.append(IndexItem(item=item, string=filter))
        self.updateIndexItems()
        info("Indexed {} bookmarks [{:d} ms]".format(len(self._index_items), (int(perf_counter_ns() - start) // 1000000)))
        self._index_items = []


    def handleTriggerQuery(self, query):
        stripped = query.string.strip()
        if stripped:
            TriggerQueryHandler.handleTriggerQuery(self, query)
        else:
            query.add(
                StandardItem( text=md_name, subtext="Search for a page saved in Readeck", iconUrls=self.iconUrls)
            )
        query.add(
            StandardItem(
                text="Refresh cache index",
                subtext="Refresh indexed bookmarks",
                iconUrls=["xdg:view-refresh"],
                actions=[Action("refresh", "Refresh readeck index", lambda: self.fetchIndexItems())],
            )
        )


    def _create_filters(self, item: dict):
        return ",".join([item["url"], item["title"], ",".join(label for label in item["labels"])])

    def _gen_item(self, bookmark: dict):
        title = bookmark["title"] or bookmark["url"]
        # Add a star for favourites
        if bookmark["is_marked"]:
            title = "⭐ " + title
        return StandardItem(
            id=str(self.id),
            text=title,
            subtext="{}: {}".format(",".join(label for label in bookmark["labels"]), bookmark["url"]),
            iconUrls=self.iconUrls,
            actions=[
                Action("open", "Open in Readeck", lambda u=bookmark["href"].replace("/api", "", 1): openUrl(u)),
                Action("open", "Open bookmark URL", lambda u=bookmark["url"]: openUrl(u)),
                Action("copy", "Copy URL to clipboard", lambda u=bookmark["url"]: setClipboardText(u)),
                Action("archive", "Archive bookmark", lambda u=bookmark["id"]: self._archive_bookmark(u)),
                Action("delete", "Delete bookmark", lambda u=bookmark["id"]: self._archive_bookmark(u)),
            ],
        )

    def _fetch_results(self):
        """Consumes the generated lists of links, and flattens them down into a single generator of link items.

        A bit confusing to read, but essentially grabs `link` generated  by each `link_list` that is in turn
        generated by `_get_links`.

        Returns:
            A generator populated with parsed link objects
        """
        return (link for link_list in self._get_links() for link in link_list)

    def _get_links(self):
        """Generator function that fetches the full collection of bookmarks.
        Will handle pagination from the API and will continue to fetch until all items are retrieved.
        Intended to be called by `_fetch_results`.

        Yields:
            A list of result objects, parsed from JSON
        """
        offset = 0
        total = 1
        headers = {"User-Agent": self.user_agent, "Authorization": f"Bearer {self._api_key}", "accept": "application/json"}
        params = {"limit": self.limit}
        response_headers = None
        while offset <= total:
            params["offset"] = offset
            url = f"{self._instance_url}/api/bookmarks?{parse.urlencode(params)}"
            response = requests.get(url, headers=headers, timeout=5)
            if response.ok:
                if not response_headers:
                    response_headers = response.headers
                    total = int(response_headers.get("Total-Count", 1))
                result = response.json() # Should just be a list of links
                offset += self.limit
                yield result
            else:
                warning(f"Got response {response.status_code} querying {url}")
                break

    def _delete_bookmark(self, bookmark_id: str):
        url = f"{self._instance_url}/api/bookmarks/{bookmark_id}"
        headers = {"User-Agent": self.user_agent, "Authorization": f"Bearer {self._api_key}"}
        debug("About to DELETE {}".format(url))
        response = requests.delete(url, headers=headers)
        if response.ok:
            self.fetchIndexItems()
        else:
            warning("Got response {}".format(response))

    def _archive_bookmark(self, bookmark_id: str):
        url = f"{self._instance_url}/api/bookmarks/{bookmark_id}/"
        headers = {"User-Agent": self.user_agent, "Authorization": f"Bearer {self._api_key}"}
        debug("About to PATCH {}".format(url))
        response = requests.patch(url, json={"is_archived": True}, headers=headers)
        if response.ok:
            self.fetchIndexItems()
        else:
            warning("Got response {}".format(response))
