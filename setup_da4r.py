<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>net48</TargetFramework>
    <AssemblyName>RoomDataExtractor</AssemblyName>
    <RootNamespace>RoomDataExtractor</RootNamespace>
    <Nullable>disable</Nullable>
    <PlatformTarget>x64</PlatformTarget>
  </PropertyGroup>

  <ItemGroup>
    <!-- DA4R NuGet-pakke (inkluderer Revit API + DesignAutomationBridge) -->
    <PackageReference Include="Autodesk.Forge.DesignAutomation.Revit" Version="2024.0.0" />
    <PackageReference Include="Newtonsoft.Json" Version="13.0.3" />
  </ItemGroup>
</Project>
