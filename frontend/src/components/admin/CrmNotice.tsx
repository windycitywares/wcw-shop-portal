import { Alert } from "@/components/ui/misc";
import { crmLink } from "@/lib/crm";

/** Says where the real work happens and links straight there. */
export function CrmNotice({ what, path, action }: { what: string; path: string; action: string }) {
  return (
    <Alert tone="info" className="mb-4">
      <span data-testid="crm-notice">
        {what} are managed in the CRM; this page is for viewing only.{" "}
        <a href={crmLink(path)} target="_blank" rel="noopener noreferrer" className="font-medium underline underline-offset-2">
          {action}
          <span className="sr-only"> (opens the CRM in a new tab)</span>
        </a>
      </span>
    </Alert>
  );
}
