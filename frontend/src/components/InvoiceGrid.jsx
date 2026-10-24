import { useMemo } from "react";
import { AgGridReact } from "ag-grid-react";
import { AllCommunityModule, ModuleRegistry } from "ag-grid-community";

ModuleRegistry.registerModules([AllCommunityModule]);

export default function InvoiceGrid({ rows, selectedId, onCall }) {
  const columnDefs = useMemo(
    () => [
      { field: "number", headerName: "Invoice", width: 100 },
      { field: "client_name", headerName: "Client", flex: 1, minWidth: 140 },
      {
        headerName: "Amount",
        width: 130,
        valueGetter: (p) => `${p.data.amount} ${p.data.currency}`,
      },
      {
        field: "days_overdue",
        headerName: "Days overdue",
        width: 140,
        sort: "desc",
        cellStyle: (p) =>
          p.value >= 30 ? { color: "#b42318", fontWeight: 600 } : null,
      },
      { field: "status", headerName: "PayPal status", width: 150 },
      {
        headerName: "Call outcome",
        width: 150,
        valueGetter: (p) => p.data.outcome || p.data.call_status || "none",
      },
      { field: "promise_date", headerName: "Promise", width: 120 },
      {
        headerName: "Owner review",
        width: 230,
        valueGetter: (p) => {
          const { escalation, owner_decision } = p.data;
          if (!escalation) return "";
          return `${escalation}: ${owner_decision || "pending"}`;
        },
      },
      {
        headerName: "",
        width: 100,
        sortable: false,
        cellRenderer: (p) => (
          <button disabled={p.data.paid} onClick={() => onCall(p.data)}>
            {p.data.paid ? "Paid" : "Open"}
          </button>
        ),
      },
    ],
    [onCall]
  );

  return (
    <div style={{ height: 330 }}>
      <AgGridReact
        rowData={rows}
        columnDefs={columnDefs}
        defaultColDef={{ sortable: true, resizable: true }}
        getRowId={(p) => p.data.id}
        getRowStyle={(p) =>
          p.data.paid
            ? { background: "#ecfdf3" }
            : p.data.id === selectedId
            ? { background: "#eef4ff" }
            : undefined
        }
      />
    </div>
  );
}