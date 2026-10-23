# Remove financial features

Currency selection and formatting, fuel costs, maintenance part prices, monetary report totals, and payment-related interface text have been removed. Lodge preferences now configure dates only. Fuel volumes, mileage, maintenance parts and quantities, service history, subscription packages and access dates remain operational.

The API no longer accepts or returns currency or monetary input/output fields in preferences, membership metadata, fuel, maintenance, parts, reports or CSV exports. Adding parts no longer recalculates historical ticket costs. Accounting integration is removed from the public feature catalogue and package comparison. Existing tenant isolation, permissions, subscription guards, CSRF, MFA and audit checks remain intact.

Historical database columns and audit records are retained to avoid destructive data loss. They are no longer exposed as active application features. This change requires no schema migration and does not delete existing records. Earlier PKR/currency setup notes are superseded by this change.

Validation: 464 API tests, the production frontend build, all 35 browser checks and the static guard audit pass. Regression checks cover rejection of monetary writes, omission of monetary API/CSV output, preservation of historical values, removal of accounting capabilities from package responses, and date preferences and fuel displays without financial controls. Responsive registration checks pass at 375, 768, 1366 and 1440 px in both themes.
