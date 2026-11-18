import { AccountsAdmin } from "@/components/admin/users/AccountsAdmin";
import { SupplierLogins } from "@/components/admin/users/SupplierLogins";

/** Team: admin, publisher and author accounts, and supplier logins. Shoppers live on /admin/users. */
export default function TeamPage() {
  return (
    <>
      <AccountsAdmin scope="team" />
      <SupplierLogins />
    </>
  );
}
