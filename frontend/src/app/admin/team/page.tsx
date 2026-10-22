import { AccountsAdmin } from "@/components/admin/users/AccountsAdmin";

/** Team: admin, publisher and author accounts. Shoppers live on /admin/users. */
export default function TeamPage() {
  return <AccountsAdmin scope="team" />;
}
