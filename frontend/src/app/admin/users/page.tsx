import { AccountsAdmin } from "@/components/admin/users/AccountsAdmin";

/** Customer accounts: every shopper who has signed up. Staff live on /admin/team. */
export default function CustomerAccountsPage() {
  return <AccountsAdmin scope="customers" />;
}
