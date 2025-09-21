#!/usr/bin/python3.9

from pathlib import Path
from subprocess import run as sub_run
from typing import Optional

_WG_ETC="/etc/wireguard/"

_WG_ETC_CONFIG="/etc/wireguard/wg0.conf"

_YAD_CHK_TRUE="TRUE"

_YAD_TITLE="Wireguard"

def util_fixstring(
		data:Optional[str],
		low:bool=False
	)->Optional[str]:

	if data is None:
		return None
	data=data.strip()
	if len(data)==0:
		return None
	if low:
		return data.lower()
	return data

def util_subrun(
		command:list,
		get_output:bool=False
	)->tuple:

	print("\n$",command)

	proc=sub_run(
		command,
		capture_output=get_output,
		text=get_output
	)

	proc_stdout:Optional[str]=None
	if proc.stdout is not None:
		proc_stdout=util_fixstring(proc.stdout)
	proc_stderr:Optional[str]=None
	if proc.stderr is not None:
		proc_stderr=util_fixstring(proc.stderr)

	return (
		proc.returncode,
		proc_stdout,
		proc_stderr
	)

def yad_message(
		text:str,
		question:bool=False
	)->bool:

	cmd=[
		"yad",
			"--image","wireguard",
			"--fixed",
			"--center",
			"--borders=8",
			"--width=320",
			"--height=160",

		"--title",_YAD_TITLE,
		"--text",text,
		"--text-align","center",
		"--buttons-layout","center",
	]

	if not question:
		cmd.append(["--escape-ok","--button","Ok:0"])

	result=util_subrun(cmd)

	if question:
		return result[0]==0

	return True

def yad_select_new_configfile()->Optional[tuple]:

	# yad --title="WireGuard" --text="Select a config file and hit OK to connect" --form --field="Config file":FL
	# yad --fixed --center --borders 8 --width 320 --height 160 --form --separator ":" --title "Wireguard" --field "Config file:FL" --field "Use as wg0:CHK"

	result=util_subrun(
		[
			"yad",
				"--image","wireguard",
				"--fixed",
				"--center",
				"--borders","8",
				"--width","320",
				"--height","160",

			"--form",
			"--separator",":",
			"--title",_YAD_TITLE,
			"--text","Select a client wireguard config file and hit the OK button to connect",
			"--field","Path to config file:FL",
			"--field","Rename and store as wg0:CHK","TRUE"
			# "--field=Config file:FL\"",
			# "--field=\"Interface name:TXT\" wg0",
		],
		get_output=True
	)

	print(result[1])

	if not result[0]==0:
		return None

	result_raw=result[1].strip()
	if result_raw.endswith(":"):
		result_raw=result_raw[:-1]

	parts=result_raw.split(":")
	if not len(parts)==2:
		return None

	tmp=util_fixstring(parts[0])
	if tmp is None:
		return None

	pl=Path(parts[0])
	if not pl.is_file():
		return None

	if pl.is_symlink():
		pl=pl.resolve()

	if pl.stat().st_size>1024*1024:
		return None

	return (
		str(pl),
		util_fixstring(parts[1])==_YAD_CHK_TRUE
	)

def wg_get_current_connection()->tuple:

	# (bool,Optional[str])

	result=util_subrun(["wg"],get_output=True)
	if not result[0]==0:
		print(result)
		return (False,None)

	return (True,result[1])

def yad_manage_current_connection(conn_status)->bool:

	result=util_subrun([
		"yad",
			"--image","wireguard",
			"--fixed",
			"--center",
			"--borders=8",
			"--width=320",
			"--height=160",

		"--form",
		"--separator","",
		"--title",_YAD_TITLE,
		"--text",conn_status,
		"--field","Disconnect:CHK"
		],
		get_output=True
	)

	if not result[0]==0:
		return False

	print(result)

	if result[1].strip()==_YAD_CHK_TRUE:
		return True

	return False

def main_new_connection()->int:

	fpath_conf_str:Optional[str]=None
	use_as_wg0=False

	while True:
		wutt=False
		result=yad_select_new_configfile()
		if result is None:
			wutt=True

		if not wutt:
			fpath_conf_str,use_as_wg0=result
			if fpath_conf_str is None:
				wutt=True

		if wutt:
			if not yad_message(
					"You have not selected a valid file. Do you want to continue?",
					question=True
				):

				break

		if not wutt:
			print("Yes")
			break

	if fpath_conf_str is None:
		return 1

	fpath_conf_pl=Path(fpath_conf_str)

	selected_conf={
		True:"wg0",
		False:fpath_conf_pl.stem
	}[use_as_wg0]

	stored=Path(_WG_ETC,fpath_conf_pl.name)
	if fpath_conf_pl.is_relative_to(_WG_ETC):
		if stored.is_file():
			stored.unlink()

	contents=Path(fpath_conf_str).read_text()
	stored.write_text(contents)

	sc=0
	while True:

		result=util_subrun(["wg-quick","up",selected_conf])
		if result is None:
			yad_message("Command failure")
			sc=255
			break

		if not result[0]==0:
			print(result)
			if yad_message(
					"Failed to connect. Try again?",
					question=True
				):
				continue

			sc=1
			break

		if result[0]==0:
			sc=0
			break

	return sc

def main_connected(conn_status:str)->int:

	user_wants_to_disconnect=yad_manage_current_connection(conn_status)

	if user_wants_to_disconnect:

		lines=conn_status.strip().splitlines()
		if len(lines)==0:
			return 1

		line_one=lines[0].strip()

		patt="interface: "
		patt_len=len(patt)

		if not line_one.startswith(patt):
			return 1

		interface_name=line_one[patt_len:].strip()
		if len(interface_name)==0:
			return 1

		result=util_subrun([
			"wg-quick",
				"down",
				interface_name
		])
		if not result[0]==0:
			return 255

		print("Interface down")

	return 0

def main()->int:

	ok,conn_state=wg_get_current_connection()
	if not ok:
		return 255

	offline=(conn_state is None)

	return_code=0

	if offline:
		return_code=main_new_connection()
		if return_code==0:
			offline=False
			ok,conn_state=wg_get_current_connection()
			if not ok:
				return 255

	if not offline:
		return_code=main_connected(conn_state)

	return return_code

if __name__=="__main__":

	from sys import exit as sys_exit

	tui=False

	return_code=main()

	sys_exit(return_code)
