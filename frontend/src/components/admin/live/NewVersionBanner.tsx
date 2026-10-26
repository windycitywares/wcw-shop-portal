"use client";

import { Button } from "@/components/ui/Button";
import { Icon } from "../ui/Icon";
import { useLiveStatus } from "./LiveProvider";

/** "A new version of the admin is out" after a deploy, like GitHub's "new code" notice. Refreshing is the person's call. */
export function NewVersionBanner() {
  const { newVersion, prefs } = useLiveStatus();
  if (!newVersion || !prefs.new_version) return null;
  return (
    <div role="status" className="flex flex-wrap items-center justify-center gap-x-4 gap-y-1 bg-accent px-4 py-2 text-sm text-white">
      <span className="flex items-center gap-2">
        <Icon name="download" className="size-4" />A new version of the admin is out. Refresh to use it; save any open edits first.
      </span>
      <Button size="sm" variant="secondary" onClick={() => window.location.reload()}>
        Refresh now
      </Button>
    </div>
  );
}
