import { AccountsAdmin } from "@/components/admin/users/AccountsAdmin";

/** Team: admin, publisher and author accounts (supplier logins are in the CRM). Shoppers live on /admin/users. */
export default function TeamPage() {
  return (
    <>
      <AccountsAdmin scope="team" />
    </>
  );
}
