import { useMemo } from "react";
import { AgGridReact } from "ag-grid-react";
import { AllCommunityModule, ModuleRegistry } from "ag-grid-community";

ModuleRegistry.registerModules([AllCommunityModule]);

export default function InvoiceGrid({ rows, selectedId, onCall }) {
  const columnDefs = useMemo(
    () => [
      { field: "number", headerName: "Invoice", minWidth: 90, maxWidth: 110 },
      { field: "client_name", headerName: "Client", minWidth: 130, flex: 1 },
      {
        headerName: "Amount",
        minWidth: 140,
        valueGetter: (p) => `${p.data.amount} ${p.data.currency}`,
      },
      {
        field: "days_overdue",
        headerName: "Days overdue",
        minWidth: 150,
        sort: "desc",
        cellStyle: (p) =>
          p.value >= 30 ? { color: "#b42318", fontWeight: 600 } : null,
      },
      { field: "status", headerName: "PayPal status", minWidth: 130 },
      {
        headerName: "Call outcome",
        minWidth: 150,
        valueGetter: (p) => {
          const { outcome, call_status, attempts, kind } = p.data;
          const tag = kind === "follow_up" ? "Follow-up: " : "";
          if (call_status === "ringing") return `${tag}Ringing (try ${attempts})`;
          if (call_status === "missed") return `${tag}Missed (try ${attempts})`;
          if (call_status === "unreachable") return "Unreachable";
          if (call_status === "awaiting_client") return `${tag}On call`;
          if (call_status === "awaiting_owner") return "Needs approval";
          return outcome || "none";
        },
      },
      { field: "promise_date", headerName: "Promise", minWidth: 110 },
      {
        field: "summary",
        headerName: "Summary",
        minWidth: 240,
        flex: 2,
        tooltipField: "summary",
      },
      {
        headerName: "",
        width: 120,
        minWidth: 120,
        maxWidth: 120,
        suppressSizeToFit: true,
        sortable: false,
        resizable: false,
        cellStyle: { padding: "0 8px" },
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
    <div style={{ height: 420 }}>
      <AgGridReact
        rowData={rows}
        columnDefs={columnDefs}
        defaultColDef={{ sortable: true, resizable: true }}
        autoSizeStrategy={{ type: "fitGridWidth" }}
        tooltipShowDelay={300}
        getRowId={(p) => p.data.id}
        getRowStyle={(p) =>
          p.data.paid
            ? { background: "#ecfdf3" }
            : p.data.outcome === "disputed"
            ? { background: "#fffaeb" }
            : p.data.id === selectedId
            ? { background: "#eef4ff" }
            : undefined
        }
      />
    </div>
  );
}