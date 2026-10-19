# Shared, non-UI palette engine. Compatible with Windows PowerShell 5.1.
function Get-FurBrushPreset([string]$Name = 'Retro Blue') {
    switch ($Name) {
        'Dark Slate' { return @{ Background='#202834'; Surface='#2b3544'; Buttons='#35445a'; Accent='#67b8ec'; Text='#edf4fc'; Borders='#647d9a' } }
        'Lavender' { return @{ Background='#eee9f8'; Surface='#ffffff'; Buttons='#e2d8f1'; Accent='#8762ba'; Text='#38234f'; Borders='#ae99c7' } }
        'Mint' { return @{ Background='#e6f4ee'; Surface='#ffffff'; Buttons='#d3eade'; Accent='#268c73'; Text='#173e34'; Borders='#91b8a8' } }
        default { return @{ Background='#e7eff8'; Surface='#ffffff'; Buttons='#dbe5ef'; Accent='#3b82c4'; Text='#17304e'; Borders='#97abc2' } }
    }
}
function ConvertTo-FurBrushHex([string]$Value) {
    if ($Value -notmatch '^#[0-9a-fA-F]{6}$') { throw "Use a six-digit color such as #3B82C4." }
    return $Value.ToLowerInvariant()
}
function Get-FurBrushShade([string]$Color, [double]$Amount) {
    $Color = ConvertTo-FurBrushHex $Color
    if ($Amount -lt -1 -or $Amount -gt 1) { throw 'Shade out of range.' }
    $target = if ($Amount -ge 0) { 255 } else { 0 }
    $mix = [Math]::Abs($Amount)
    $rgb = @()
    foreach ($offset in @(1,3,5)) {
        $channel = [Convert]::ToInt32($Color.Substring($offset,2),16)
        $rgb += [int][Math]::Round($channel + ($target-$channel)*$mix)
    }
    return ('#{0:x2}{1:x2}{2:x2}' -f $rgb[0],$rgb[1],$rgb[2])
}
function Get-FurBrushSelectionText([string]$Color) {
    $Color = ConvertTo-FurBrushHex $Color
    $channels = @()
    foreach ($offset in @(1,3,5)) {
        $c = [Convert]::ToInt32($Color.Substring($offset,2),16) / 255.0
        $channels += $(if ($c -le 0.04045) { $c/12.92 } else { [Math]::Pow(($c+0.055)/1.055,2.4) })
    }
    $luminance = .2126*$channels[0]+.7152*$channels[1]+.0722*$channels[2]
    # Pick the larger contrast ratio against the solid accent color.
    if ((1.05/($luminance+.05)) -ge (($luminance+.05)/.05)) { return '#ffffff' }
    return '#000000'
}
function ConvertTo-FurBrushTheme([string]$Template, [hashtable]$Palette) {
    $colors = @{}
    foreach ($key in @('Background','Surface','Buttons','Accent','Text','Borders')) {
        if (-not $Palette.ContainsKey($key)) { throw "Missing color: $key" }
        $colors[$key] = ConvertTo-FurBrushHex ([string]$Palette[$key])
    }
    $colors.SelectionText = Get-FurBrushSelectionText $colors.Accent
    $rendered = [regex]::Replace($Template, '\{\{([A-Za-z]+):(-?[0-9.]+)\}\}', {
        param($match)
        $key = $match.Groups[1].Value
        if (-not $colors.ContainsKey($key)) { throw "Unknown theme color: $key" }
        $shade = [double]::Parse($match.Groups[2].Value,[Globalization.CultureInfo]::InvariantCulture)
        # Keep glossy highlights restrained on dark button palettes.
        if ($key -eq 'Buttons' -and $shade -gt 0) {
            $brightness = 0
            foreach ($offset in @(1,3,5)) { $brightness += [Convert]::ToInt32($colors.Buttons.Substring($offset,2),16) }
            if ($brightness -lt 330) { $shade *= 0.18 }
        }
        return Get-FurBrushShade $colors[$key] $shade
    })
    if ($rendered.Contains('{{')) { throw 'Unresolved theme template token.' }
    return $rendered
}
function Save-FurBrushTheme([string]$Directory,[hashtable]$Palette) {
    $templatePath = Join-Path $Directory 'themes/Windows7-Retro.template.qss'
    $themePath = Join-Path $Directory 'themes/Windows7-Retro.qss'
    $settingsPath = Join-Path $Directory 'themes/colors.json'
    $template = [IO.File]::ReadAllText($templatePath)
    $theme = ConvertTo-FurBrushTheme $template $Palette
    $id = [Guid]::NewGuid().ToString('N')
    $themeTemp = $themePath + '.' + $id + '.tmp'
    $settingsTemp = $settingsPath + '.' + $id + '.tmp'
    $backup = $null
    try {
        [IO.File]::WriteAllText($themeTemp,$theme,[Text.UTF8Encoding]::new($false))
        [IO.File]::WriteAllText($settingsTemp,($Palette | ConvertTo-Json),[Text.UTF8Encoding]::new($false))
        if ([IO.File]::Exists($themePath)) {
            $backupDir = Join-Path $Directory 'themes/backups'
            [IO.Directory]::CreateDirectory($backupDir) | Out-Null
            $backup = Join-Path $backupDir (('theme-{0}-{1}.qss' -f (Get-Date -Format 'yyyyMMdd-HHmmss'),$id))
            [IO.File]::Copy($themePath,$backup,$false)
        }
        Move-Item -LiteralPath $themeTemp -Destination $themePath -Force
        try {
            Move-Item -LiteralPath $settingsTemp -Destination $settingsPath -Force
        } catch {
            throw 'Theme was saved, but color preferences could not be saved. Reopen the editor to check them.'
        }
    } finally {
        foreach ($temp in @($themeTemp,$settingsTemp)) {
            if ([IO.File]::Exists($temp)) { [IO.File]::Delete($temp) }
        }
    }
    return $backup
}
