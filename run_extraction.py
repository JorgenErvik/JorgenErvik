using Autodesk.Revit.ApplicationServices;
using Autodesk.Revit.DB;
using Autodesk.Revit.DB.Architecture;
using DesignAutomationFramework;
using Newtonsoft.Json;
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;

[assembly: Autodesk.Revit.Attributes.Transaction(Autodesk.Revit.Attributes.TransactionMode.Manual)]
[assembly: Autodesk.Revit.Attributes.Regeneration(Autodesk.Revit.Attributes.RegenerationOption.Manual)]

namespace RoomDataExtractor
{
    public class ExtractRoomsApp : IExternalDBApplication
    {
        private static readonly string[] FEF_PARAMS = new[]
        {
            "FEF Romtype",
            "FEF Romtype beskrivelse",
            "FEF_Romkategori",
            "NS3457_Romfunksjon",
            "NS3457_Beskrivelse",
            "FEF_OperationalStatus",
        };

        public ExternalDBApplicationResult OnStartup(ControlledApplication app)
        {
            DesignAutomationBridge.DesignAutomationReadyEvent += HandleReady;
            return ExternalDBApplicationResult.Succeeded;
        }

        public ExternalDBApplicationResult OnShutdown(ControlledApplication app)
        {
            return ExternalDBApplicationResult.Succeeded;
        }

        private void HandleReady(object sender, DesignAutomationReadyEventArgs e)
        {
            e.Succeeded = true;
            try
            {
                Run(e.DesignAutomationData);
            }
            catch (Exception ex)
            {
                Console.WriteLine($"FEIL: {ex.Message}");
                e.Succeeded = false;
            }
        }

        private void Run(DesignAutomationData data)
        {
            var doc = data.RevitDoc;
            Console.WriteLine($"Behandler: {doc.Title}");

            var rooms = new FilteredElementCollector(doc)
                .OfCategory(BuiltInCategory.OST_Rooms)
                .WhereElementIsNotElementType()
                .Cast<Room>()
                .Where(r => r.Area > 0)
                .ToList();

            Console.WriteLine($"Fant {rooms.Count} rom");

            var result = new List<Dictionary<string, object>>();

            foreach (var room in rooms)
            {
                var dict = new Dictionary<string, object>
                {
                    ["Revit_ID"]    = room.Id.IntegerValue,
                    ["Romnummer"]   = room.Number ?? "",
                    ["Romnavn"]     = room.Name ?? "",
                    ["Etasje"]      = room.Level?.Name ?? "",
                    ["Areal_m2"]    = Math.Round(room.Area * 0.092903, 2), // sq ft → m²
                };

                foreach (var pname in FEF_PARAMS)
                {
                    var p = room.LookupParameter(pname);
                    if (p != null)
                    {
                        dict[pname] = p.StorageType == StorageType.Double
                            ? (object)p.AsDouble()
                            : p.AsString() ?? "";
                    }
                    else
                    {
                        dict[pname] = "";
                    }
                }

                result.Add(dict);
            }

            var output = new
            {
                modell   = doc.Title,
                antall   = result.Count,
                rom      = result,
            };

            File.WriteAllText("output.json", JsonConvert.SerializeObject(output, Formatting.Indented));
            Console.WriteLine("Skrevet output.json");
        }
    }
}
