"use client";

import { usePathname } from "next/navigation";
import { Popover } from "@/components/ui/Popover";
import { Icon } from "./ui/Icon";
import { helpFor } from "@/lib/adminHelp";

/** A "?" button in the admin header that explains the page you're on. */
export function HelpButton() {
  const pathname = usePathname();
  const entry = helpFor(pathname);
  if (!entry) return null;
  return (
    <Popover
      label="Help for this page"
      title="Help for this page"
      trigger={
        <span aria-hidden="true" className="grid size-5 place-items-center rounded-full border border-line text-xs font-semibold text-muted">
          ?
        </span>
      }
      triggerClassName="h-9 w-9 justify-center border-transparent bg-transparent px-0 hover:border-transparent hover:bg-sand"
      panelClassName="w-80 p-0"
      align="right"
    >
      {(close) => (
        <div className="p-4">
          <p className="text-sm font-medium">{entry.title}</p>
          <div className="mt-2 space-y-2 text-sm text-muted">
            {entry.body.map((p, i) => (
              <p key={i}>{p}</p>
            ))}
          </div>
          <button
            type="button"
            onClick={close}
            className="mt-3 text-xs text-muted underline hover:text-ink"
          >
            Close
          </button>
        </div>
      )}
    </Popover>
  );
}
