$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'FurBrush-Colors.ps1')
Add-Type -AssemblyName @('PresentationFramework','PresentationCore','WindowsBase','System.Windows.Forms','System.Drawing')
[xml]$layout = @'
<Window xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
 xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml" Title="FurBrush - UI Colors"
 Width="660" Height="650" MinWidth="660" MinHeight="650" WindowStartupLocation="CenterScreen"
 Background="#edf3fa" FontFamily="Segoe UI" FontSize="13">
 <Grid Margin="24">
  <Grid.RowDefinitions><RowDefinition Height="Auto"/><RowDefinition Height="Auto"/><RowDefinition Height="Auto"/><RowDefinition Height="*"/><RowDefinition Height="Auto"/></Grid.RowDefinitions>
  <StackPanel><TextBlock Text="Make FurBrush yours" FontSize="25" Foreground="#17304e"/>
   <TextBlock Text="Choose colors, save, then restart FurBrush to apply." Margin="0,6,0,16"/></StackPanel>
  <StackPanel Grid.Row="1" Orientation="Horizontal" Margin="0,0,0,14">
   <TextBlock Text="Preset" VerticalAlignment="Center" Margin="0,0,12,0"/>
   <ComboBox x:Name="Presets" Width="190"><ComboBoxItem Content="Retro Blue"/><ComboBoxItem Content="Dark Slate"/><ComboBoxItem Content="Lavender"/><ComboBoxItem Content="Mint"/></ComboBox>
  </StackPanel>
  <StackPanel x:Name="ColorRows" Grid.Row="2"/>
  <Border x:Name="Preview" Grid.Row="3" BorderThickness="1" Padding="16" Margin="0,12,0,12">
   <StackPanel><TextBlock x:Name="PreviewTitle" Text="FurBrush preview" FontSize="19"/>
    <Border x:Name="PreviewSurface" BorderThickness="1" Padding="9" Margin="0,10,0,10"><TextBlock x:Name="PreviewText" Text="Your groom settings and input fields"/></Border>
    <StackPanel Orientation="Horizontal"><Border x:Name="PreviewButton" BorderThickness="1" Padding="12,6"><TextBlock x:Name="ButtonText" Text="Example button"/></Border>
     <Border x:Name="PreviewAccent" Padding="12,6" Margin="10,0,0,0"><TextBlock x:Name="AccentText" Text="Selection"/></Border></StackPanel>
   </StackPanel>
  </Border>
  <StackPanel Grid.Row="4"><TextBlock x:Name="Status" Text="A backup of your current theme is kept each time you save." TextWrapping="Wrap" Margin="0,0,0,12"/>
   <StackPanel Orientation="Horizontal" HorizontalAlignment="Right"><Button x:Name="SaveButton" Content="Save colors" Padding="18,7" Margin="0,0,10,0"/><Button x:Name="CloseButton" Content="Close" Padding="18,7"/></StackPanel>
  </StackPanel>
 </Grid>
</Window>
'@
$window = [Windows.Markup.XamlReader]::Load([Xml.XmlNodeReader]::new($layout))
$inputs = @{}; $swatches = @{}
$labels = [ordered]@{ Background='Window background'; Surface='Input fields / lists'; Buttons='Buttons / toolbars'; Accent='Highlights'; Text='Text'; Borders='Borders' }
function Get-EditorPalette {
    $result = @{}
    foreach ($key in $labels.Keys) { $result[$key] = ConvertTo-FurBrushHex $inputs[$key].Text }
    return $result
}
function Update-ColorPreview {
    try {
        $palette = Get-EditorPalette
        foreach ($key in $labels.Keys) { $swatches[$key].Background = [Windows.Media.BrushConverter]::new().ConvertFromString($palette[$key]) }
        $convert = [Windows.Media.BrushConverter]::new()
        $bg = $convert.ConvertFromString($palette.Background)
        $text = $convert.ConvertFromString($palette.Text)
        $border = $convert.ConvertFromString($palette.Borders)
        $window.FindName('Preview').Background = $bg
        $window.FindName('Preview').BorderBrush = $border
        $window.FindName('PreviewTitle').Foreground = $text
        $window.FindName('PreviewSurface').Background = $convert.ConvertFromString($palette.Surface)
        $window.FindName('PreviewSurface').BorderBrush = $border
        $window.FindName('PreviewText').Foreground = $text
        $window.FindName('PreviewButton').Background = $convert.ConvertFromString($palette.Buttons)
        $window.FindName('PreviewButton').BorderBrush = $border
        $window.FindName('ButtonText').Foreground = $text
        $window.FindName('PreviewAccent').Background = $convert.ConvertFromString($palette.Accent)
        $window.FindName('AccentText').Foreground = $convert.ConvertFromString((Get-FurBrushSelectionText $palette.Accent))
        $window.FindName('SaveButton').IsEnabled = $true
    } catch { $window.FindName('SaveButton').IsEnabled = $false }
}
foreach ($key in $labels.Keys) {
    $row = [Windows.Controls.Grid]::new();$row.Margin = [Windows.Thickness]::new(0,0,0,8)
    foreach ($width in @('200','100','*','90')) {
        $column = [Windows.Controls.ColumnDefinition]::new()
        $column.Width = [Windows.GridLengthConverter]::new().ConvertFromString($width)
        $row.ColumnDefinitions.Add($column)
    }
    $label = [Windows.Controls.TextBlock]::new();$label.Text=$labels[$key];$label.VerticalAlignment='Center';$row.Children.Add($label)|Out-Null
    $box = [Windows.Controls.TextBox]::new();$box.Margin=[Windows.Thickness]::new(0,0,10,0);$box.Padding=[Windows.Thickness]::new(5);[Windows.Controls.Grid]::SetColumn($box,1);$row.Children.Add($box)|Out-Null;$inputs[$key]=$box
    $swatch = [Windows.Controls.Border]::new();$swatch.BorderThickness=[Windows.Thickness]::new(1);$swatch.BorderBrush=[Windows.Media.Brushes]::Gray;$swatch.Margin=[Windows.Thickness]::new(0,0,10,0);[Windows.Controls.Grid]::SetColumn($swatch,2);$row.Children.Add($swatch)|Out-Null;$swatches[$key]=$swatch
    $pick = [Windows.Controls.Button]::new();$pick.Content='Choose...';$pick.Tag=$key;[Windows.Controls.Grid]::SetColumn($pick,3);$row.Children.Add($pick)|Out-Null
    $pick.Add_Click({
        param($sender,$eventArgs)
        $key = [string]$sender.Tag
        $dialog = [Windows.Forms.ColorDialog]::new();$dialog.FullOpen=$true
        try {
            try { $dialog.Color=[Drawing.ColorTranslator]::FromHtml((ConvertTo-FurBrushHex $inputs[$key].Text)) } catch { }
            if ($dialog.ShowDialog() -eq [Windows.Forms.DialogResult]::OK) {
                $inputs[$key].Text = '#{0:x2}{1:x2}{2:x2}' -f $dialog.Color.R,$dialog.Color.G,$dialog.Color.B
            }
        } finally { $dialog.Dispose() }
    })
    $window.FindName('ColorRows').Children.Add($row)|Out-Null
}
$palette = Get-FurBrushPreset
$settingsPath = Join-Path $PSScriptRoot 'themes/colors.json'
if (Test-Path -LiteralPath $settingsPath) {
    try {
        $saved = [IO.File]::ReadAllText($settingsPath) | ConvertFrom-Json
        foreach ($key in $labels.Keys) { $palette[$key] = ConvertTo-FurBrushHex ([string]$saved.$key) }
    } catch { $window.FindName('Status').Text='Could not load saved preferences. Default colors are shown.'; $palette=Get-FurBrushPreset }
}
foreach ($key in $labels.Keys) { $inputs[$key].Text=$palette[$key];$inputs[$key].Add_TextChanged({ Update-ColorPreview }) }
$window.FindName('Presets').Add_SelectionChanged({
    $preset = Get-FurBrushPreset ([string]$window.FindName('Presets').SelectedItem.Content)
    foreach ($key in $labels.Keys) { $inputs[$key].Text=$preset[$key] }
    Update-ColorPreview
})
$window.FindName('SaveButton').Add_Click({
    try {
        $palette = Get-EditorPalette
        $backup = Save-FurBrushTheme $PSScriptRoot $palette
        $window.FindName('Status').Text='Colors saved. Restart FurBrush through its launcher to apply. Previous theme is in themes/backups.'
    } catch {
        [Windows.MessageBox]::Show($_.Exception.Message,'Could not save colors') | Out-Null
    }
})
$window.FindName('CloseButton').Add_Click({ $window.Close() })
Update-ColorPreview
$window.ShowDialog()|Out-Null
