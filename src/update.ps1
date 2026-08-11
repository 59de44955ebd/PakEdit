[System.Reflection.Assembly]::LoadWithPartialName("System.Windows.Forms")

[float]$version = $args[0]
[string]$base_url = $args[1]
[string]$setup_exe = $args[2]

$tag = ([xml](Invoke-WebRequest -UseBasicParsing "$base_url/tags.atom").Content).feed.entry[0].title
if($tag.Substring(1) -gt $version)
{
	If ($setup_exe -eq "")
	{
		$msgboxresult = [System.Windows.Forms.MessageBox]::Show("A newer version was found. Download it now?","Update Checker",4,[System.Windows.Forms.MessageBoxIcon]::Question)
		If ($msgboxresult -eq "Yes")
		{
			Start-Process "$base_url/releases/$tag"
		}
	}
	else
	{
		$msgboxresult = [System.Windows.Forms.MessageBox]::Show("A newer version was found. Do you want to install it now?`n`nAnswering 'Yes' will quit the application.","Update Checker",4,[System.Windows.Forms.MessageBoxIcon]::Question)
		If ($msgboxresult -eq "Yes")
		{
		    Stop-Process -Name "PakEdit"
			Invoke-WebRequest -Uri "$base_url/releases/download/$tag/$setup_exe" -OutFile "$Env:TMP\$setup_exe"
			Start-Process -FilePath "$Env:TMP\$setup_exe"
		}
	}
}
else
{
	[System.Windows.Forms.MessageBox]::Show("You are already using the latest version.","Update Checker",0,[System.Windows.Forms.MessageBoxIcon]::Information)
}
