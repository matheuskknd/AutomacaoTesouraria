#!/usr/bin/env python3.10
# -*- coding: UTF-8 -*-

from argparse import (ArgumentParser, FileType, Namespace)
from contextlib import redirect_stderr, redirect_stdout
from datetime import (datetime, timedelta, date)
import xml.etree.ElementTree as ET
from typing import Any, TextIO
from requests import Response
# from base64 import b64encode
from os.path import join
import logging as log
from os import getcwd
import traceback
import xmltodict
import requests
import random
import json
import re

with open('CONFIG.json', 'r') as f:
  CONFIG: dict[str, Any] = json.load(f)
  del f

################################
###### Abstraction Layer  ######
################################


def sendSoapRequest(url: str, headers: dict[str, Any], data: bytes) -> Response:
  log.debug(f"Request:")
  print(url)
  print(f"{json.dumps(headers, ensure_ascii=False, indent=2)}")
  print(data.decode("UTF-8"))
  resp: Response = requests.post(url, data=data, headers=headers)
  print(f"Response:\n{resp.text}")
  return resp


################################
####### Converting Class #######
################################


class Converter:

  @staticmethod
  def calcula_barra(linha: str) -> str:
    barra: str = "".join(filter(str.isdigit, linha))

    assert Converter.modulo11_banco("34191000000000000001753980229122525005423000") == 1, (
      "Função 'modulo11_banco' está com erro!")

    if len(barra) < 47:
      barra += "0" * (47 - len(barra))

    assert len(barra) == 47, (f"A linha do código de barras está incompleta! {len(barra)}")

    barra = (barra[:4] + barra[32:47] + barra[4:9] + barra[10:20] + barra[21:31])

    assert Converter.modulo11_banco(barra[:4] + barra[5:]) == int(barra[4]), (
      f"Digito verificador {barra[4]}, o correto é {Converter.modulo11_banco(barra[:4] + barra[5:])}\n"
      "O sistema não altera automaticamente o dígito correto na quinta casa!")

    return barra

  @staticmethod
  def calcula_linha(barra: str, digitsOnly: bool = True) -> str:
    linha: str = "".join(filter(str.isdigit, barra))

    assert Converter.modulo10("399903512") == 8, ("Função 'modulo10' está com erro!")
    assert len(linha) == 44, ("A linha do código de barras está incompleta!")

    campo1: str = linha[:4] + linha[19] + "." + linha[20:24]
    campo2: str = linha[24:29] + "." + linha[29:34]
    campo3: str = linha[34:39] + "." + linha[39:44]
    campo4: str = linha[4]  # Digito verificador
    campo5: str = linha[5:19]  # Vencimento + Valor

    assert Converter.modulo11_banco(linha[:4] + linha[5:]) == int(campo4), (
      f"Digito verificador {campo4}, o correto é {Converter.modulo11_banco(linha[:4] + linha[5:])}\n"
      "O sistema não altera automaticamente o dígito correto na quinta casa!")

    if campo5 == "0":
      campo5 = "000"

    linha = (f"{campo1}{Converter.modulo10(campo1)} "
             f"{campo2}{Converter.modulo10(campo2)} "
             f"{campo3}{Converter.modulo10(campo3)} "
             f"{campo4} "
             f"{campo5}")

    return linha if not digitsOnly else "".join(filter(str.isdigit, linha))

  @staticmethod
  def modulo10(numero: str) -> int:
    numero = "".join(filter(str.isdigit, numero))
    soma: int = 0
    peso: int = 2
    contador: int = len(numero) - 1

    while contador >= 0:
      multiplicacao: int = int(numero[contador]) * peso
      if multiplicacao >= 10:
        multiplicacao = 1 + (multiplicacao-10)
      soma += multiplicacao
      if peso == 2:
        peso = 1
      else:
        peso = 2
      contador -= 1

    digito: int = 10 - (soma%10)
    if digito == 10:
      digito = 0

    return digito

  @staticmethod
  def modulo11_banco(numero: str) -> int:
    numero = "".join(filter(str.isdigit, numero))
    soma: int = 0
    peso: int = 2
    base: int = 9
    contador: int = len(numero) - 1

    for i in range(contador, -1, -1):
      soma += int(numero[i]) * peso
      if peso < base:
        peso += 1
      else:
        peso = 2

    digito: int = 11 - (soma%11)
    if digito > 9:
      digito = 0

    if digito == 0:
      digito = 1

    return digito


################################
########## Main Calls ##########
################################


def consultaTitulo2(numCodBarras: str) -> dict[str, Any]:
  # Convert the input
  # assert len(numCodBarras) == 44
  try:
    _ = Converter.calcula_linha(numCodBarras)

  except AssertionError:
    numCodBarras = Converter.calcula_barra(numCodBarras)

  payload: str = f"""
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:tem="http://tempuri.org/">
   <soapenv:Header/>
   <soapenv:Body>
      <tem:ConsultaTitulo2>
         <tem:ISPBPartRecbdrPrincipal>54403563</tem:ISPBPartRecbdrPrincipal>
         <tem:ISPBPartRecbdrAdmtd>54403563</tem:ISPBPartRecbdrAdmtd>
         <tem:NumCodBarras>{numCodBarras}</tem:NumCodBarras>
         <tem:Valor>0</tem:Valor>
         <tem:Timeout>10</tem:Timeout>
      </tem:ConsultaTitulo2>
   </soapenv:Body>
</soapenv:Envelope>
    """

  # Send it
  payload = re.sub(r"\n[ \t]*", "", payload)
  assert ET.tostring(ET.fromstring(payload), encoding="unicode") != "", payload
  resp: Response = sendSoapRequest(
    CONFIG["WS"]["url_ABGRWS"],
    headers={
      "SOAPAction": "http://tempuri.org/ConsultaTitulo2",
      "Content-Type": "text/xml;charset=UTF-8"
    },
    data=payload.encode("UTF-8"),
  )

  jsonResp: dict[str, Any] = xmltodict.parse(resp.text)
  jsonResp = jsonResp["soap:Envelope"]["soap:Body"]["ConsultaTitulo2Response"]["ConsultaTitulo2Result"]
  if "XmlR1" in jsonResp:
    return xmltodict.parse(jsonResp["XmlR1"])["DDA0110R1"]
  else:
    return dict()


def calculaValorCobrar(dda0110R1: dict[str, Any]) -> str | dict[str, Any]:
  # Auxiliar constant
  DtVencTit_D0: str = dda0110R1["DtVencTit"]
  DtVencTit_D1: str = (date.fromisoformat(DtVencTit_D0) +
                       timedelta(days=1)).strftime(r'%Y-%m-%d')

  # Fallback for TpModlCalc=2
  if (int(dda0110R1["TpModlCalc"]) == 2 and
      date.fromisoformat(DtVencTit_D0) < date.today() and
      "Grupo_DDA0110R1_Calc" not in dda0110R1):
    log.info("Boleto com modelo de cálculo 2 vencido e sem 'Grupo_DDA0110R1_Calc'"
             " está em desconformidade com a especificação..."
             "\nRetornando valor nominal como fallback.")
    return dda0110R1["VlrTit"]

  # Fallback for TpModlCalc=3 and TpModlCalc=4
  if int(dda0110R1["TpModlCalc"]) in {3, 4} and "Grupo_DDA0110R1_Calc" not in dda0110R1:
    log.info("Boleto com modelo de cálculo 3 ou 4 e sem 'Grupo_DDA0110R1_Calc'"
             " está em desconformidade com a especificação..."
             "\nRetornando valor nominal como fallback.")
    return dda0110R1["VlrTit"]

  # List of repeatable groups
  JurosTitList: list[dict[str, Any]] = [dict()]
  MultaTitList: list[dict[str, Any]] = [dict()]
  DescontoList: list[dict[str, Any]] = [dict()]
  CalcList: list[dict[str, Any]] = []

  # Process juros
  if "Grupo_DDA0110R1_JurosTit" in dda0110R1:
    if isinstance(dda0110R1["Grupo_DDA0110R1_JurosTit"], dict):
      JurosTitList = [dda0110R1["Grupo_DDA0110R1_JurosTit"]]
    elif isinstance(dda0110R1["Grupo_DDA0110R1_JurosTit"], list):
      JurosTitList = dda0110R1["Grupo_DDA0110R1_JurosTit"]
    else:
      assert False

    # List with passed dates sorted (older < newer)
    JurosTitList = sorted(
      filter(
        lambda i: date.fromisoformat(i.get("DtJurosTit", DtVencTit_D1)) <= date.
        today(), JurosTitList),
      key=lambda i: date.fromisoformat(i.get("DtJurosTit", DtVencTit_D1)))

    if len(JurosTitList) == 0:
      JurosTitList = [dict()]

  # Process multa
  if "Grupo_DDA0110R1_MultaTit" in dda0110R1:
    if isinstance(dda0110R1["Grupo_DDA0110R1_MultaTit"], dict):
      MultaTitList = [dda0110R1["Grupo_DDA0110R1_MultaTit"]]
    elif isinstance(dda0110R1["Grupo_DDA0110R1_MultaTit"], list):
      MultaTitList = dda0110R1["Grupo_DDA0110R1_MultaTit"]
    else:
      assert False

    # List with passed dates sorted (older < newer)
    MultaTitList = sorted(
      filter(
        lambda i: date.fromisoformat(i.get("DtMultaTit", DtVencTit_D1)) <= date.
        today(), MultaTitList),
      key=lambda i: date.fromisoformat(i.get("DtMultaTit", DtVencTit_D1)))

    if len(MultaTitList) == 0:
      MultaTitList = [dict()]

  # Process desconto
  if "Grupo_DDA0110R1_DesctTit" in dda0110R1:
    if isinstance(dda0110R1["Grupo_DDA0110R1_DesctTit"], dict):
      DescontoList = [dda0110R1["Grupo_DDA0110R1_DesctTit"]]
    elif isinstance(dda0110R1["Grupo_DDA0110R1_DesctTit"], list):
      DescontoList = dda0110R1["Grupo_DDA0110R1_DesctTit"]
    else:
      assert False

    # List with present and future dates sorted (older < newer)
    DescontoList = sorted(
      filter(
        lambda i: date.fromisoformat(i.get("DtDesctTit", DtVencTit_D0)) >= date.
        today(), DescontoList),
      key=lambda i: date.fromisoformat(i.get("DtDesctTit", DtVencTit_D0)))

    if len(DescontoList) == 0:
      DescontoList = [dict()]

  # Process Calc
  if "Grupo_DDA0110R1_Calc" in dda0110R1:
    if isinstance(dda0110R1["Grupo_DDA0110R1_Calc"], dict):
      CalcList = [dda0110R1["Grupo_DDA0110R1_Calc"]]
    elif isinstance(dda0110R1["Grupo_DDA0110R1_Calc"], list):
      CalcList = dda0110R1["Grupo_DDA0110R1_Calc"]
    else:
      assert False

    # List with present and future dates sorted (older < newer)
    CalcList = sorted(
      filter(lambda i: date.fromisoformat(i["DtValiddCalc"]) >= date.today(),
             CalcList), key=lambda i: date.fromisoformat(i["DtValiddCalc"]))

    if len(CalcList) == 0:
      log.info("Boleto com modelo de cálculo 2 vencido, 3 ou 4 e sem "
               "'Grupo_DDA0110R1_Calc' ainda vigente está em "
               "desconformidade com a especificação..."
               "\nRetornando valor nominal como fallback.")
      return dda0110R1["VlrTit"]

  payload: str = f"""
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:cal="http://calculotitulocipws.utils.autbank.com.br">
	<soapenv:Header/>
	<soapenv:Body>
		<cal:calculaValorCobrar>
			<cal:modeloCalculo>{dda0110R1['TpModlCalc']}</cal:modeloCalculo>
			<cal:codEspecieTitulo>{dda0110R1['CodEspTit']}</cal:codEspecieTitulo>
			<cal:codPraca>000</cal:codPraca>
			<cal:tipoJuros>{JurosTitList[-1].get('CodJurosTit', '')}</cal:tipoJuros>
			<cal:tipoMulta>{MultaTitList[-1].get('CodMultaTit', '')}</cal:tipoMulta>
			<cal:dataVencimentoTitulo>{date.fromisoformat(DtVencTit_D0).strftime(r'%d/%m/%Y')}</cal:dataVencimentoTitulo>
			<cal:dataOperacao>{date.today().strftime(r'%d/%m/%Y')}</cal:dataOperacao>
			<cal:dataJuros>{date.fromisoformat(JurosTitList[-1].get("DtJurosTit", DtVencTit_D1)).strftime(r'%d/%m/%Y')}</cal:dataJuros>
			<cal:dataMulta>{date.fromisoformat(MultaTitList[-1].get("DtMultaTit", DtVencTit_D1)).strftime(r'%d/%m/%Y')}</cal:dataMulta>
			<cal:valorTitulo>{dda0110R1['VlrTit']}</cal:valorTitulo>
			<cal:valorJuros>{JurosTitList[-1].get('Vlr_PercJurosTit', '')}</cal:valorJuros>
			<cal:valorMulta>{MultaTitList[-1].get('Vlr_PercMultaTit', '')}</cal:valorMulta>
			<cal:valorAbatimento>{dda0110R1['VlrAbattTit']}</cal:valorAbatimento>
			<cal:valorSaldoTotalAtualPagtoTitulo>{dda0110R1.get('VlrTotPgto', '')}</cal:valorSaldoTotalAtualPagtoTitulo>
			<cal:valorJurosCalculado1>{CalcList[0]['Vlr_PercJurosTit'] if len(CalcList) > 0 else ''}</cal:valorJurosCalculado1>
			<cal:valorMultaCalculado1>{CalcList[0]['VlrCalcdMulta'] if len(CalcList) > 0 else ''}</cal:valorMultaCalculado1>
			<cal:valorDescontoCalculado1>{CalcList[0]['VlrCalcdDesct'] if len(CalcList) > 0 else ''}</cal:valorDescontoCalculado1>
			<cal:valorTotalCobrar1>{CalcList[0]['VlrTotCobrar'] if len(CalcList) > 0 else ''}</cal:valorTotalCobrar1>
			<cal:dataValidadeCalculo1>{date.fromisoformat(CalcList[0]['DtValiddCalc']).strftime(r'%d/%m/%Y') if len(CalcList) > 0 else ''}</cal:dataValidadeCalculo1>
			<cal:valorJurosCalculado2/>
			<cal:valorMultaCalculado2/>
			<cal:valorDescontoCalculado2/>
			<cal:valorTotalCobrar2/>
			<cal:dataValidadeCalculo2/>
			<cal:valorJurosCalculado3/>
			<cal:valorMultaCalculado3/>
			<cal:valorDescontoCalculado3/>
			<cal:valorTotalCobrar3/>
			<cal:dataValidadeCalculo3/>
			<cal:valorJurosCalculado4/>
			<cal:valorMultaCalculado4/>
			<cal:valorDescontoCalculado4/>
			<cal:valorTotalCobrar4/>
			<cal:dataValidadeCalculo4/>
			<cal:valorJurosCalculado5/>
			<cal:valorMultaCalculado5/>
			<cal:valorDescontoCalculado5/>
			<cal:valorTotalCobrar5/>
			<cal:dataValidadeCalculo5/>
			<cal:tipoDesconto1>{DescontoList[0].get('CodDesctTit', '')}</cal:tipoDesconto1>
			<cal:dataDesconto1>{date.fromisoformat(DescontoList[0].get("DtDesctTit", DtVencTit_D0)).strftime(r'%d/%m/%Y')}</cal:dataDesconto1>
			<cal:valorDesconto1>{DescontoList[0].get('Vlr_PercDesctTit', '')}</cal:valorDesconto1>
			<cal:tipoDesconto2/>
			<cal:dataDesconto2/>
			<cal:valorDesconto2/>
			<cal:tipoDesconto3/>
			<cal:dataDesconto3/>
			<cal:valorDesconto3/>
			<cal:baixasOperacionais/>
			<cal:baixasEfetivas/>
		</cal:calculaValorCobrar>
	</soapenv:Body>
</soapenv:Envelope>
    """

  # Send it
  payload = re.sub(r"\n[ \t]*", "", payload)
  assert ET.tostring(ET.fromstring(payload), encoding="unicode") != "", payload
  resp: Response = sendSoapRequest(
    CONFIG["WS"]["url_ABWJWS"],
    headers={
      "SOAPAction": "",
    },
    data=payload.encode("UTF-8"),
  )

  jsonResp: dict[str, Any] = xmltodict.parse(resp.text)
  jsonResp = jsonResp["soapenv:Envelope"]["soapenv:Body"]
  if "calculaValorCobrarResponse" not in jsonResp:
    return jsonResp["soapenv:Fault"]

  jsonResp = jsonResp["calculaValorCobrarResponse"]["calculaValorCobrarReturn"]
  try:
    if float(jsonResp["valorTotalCobrar"]) != 0.00:
      return jsonResp["valorTotalCobrar"]
    else:
      raise Exception()

  except Exception:
    return jsonResp["valorTituloOriginal"]


def gerarRequisicao_STR0004(
  nroOrigem: str,
  vlrBruto: str,
  *,
  complemento: str,
  cnpjCpfFav: str,
  nroContaFav: str = "",
) -> dict[str, Any]:
  payload: str = f"""
<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/" xmlns:lit="http://literal.autbank.com.br">
	<soap:Body>
		<lit:gerarRequisicao>
			<lit:tipLiquidacao>{CONFIG['WS']['TS']['STR0004']['tipLiquidacao']}</lit:tipLiquidacao>
			<lit:datCadastro>{date.today().strftime(r'%d/%m/%Y')}</lit:datCadastro>
			<lit:datRequisicao>{date.today().strftime(r'%d/%m/%Y')}</lit:datRequisicao>
			<lit:datLiquidacao>{date.today().strftime(r'%d/%m/%Y')}</lit:datLiquidacao>
			<lit:datHoraLiquidacao>{date.today().strftime(r'%d/%m/%Y')} 00:00</lit:datHoraLiquidacao>

			<lit:codSisOrigem>{CONFIG['WS']['TS']['codSisOrigem']}</lit:codSisOrigem>
			<lit:nroOrigem>{nroOrigem}</lit:nroOrigem>
			<lit:codColigadaCad>{CONFIG['WS']['TS']['codColigadaCad']}</lit:codColigadaCad>
			<lit:codAgenciaCad>{CONFIG['WS']['TS']['codAgenciaCad']}</lit:codAgenciaCad>
			<lit:codDeptoCad>{CONFIG['WS']['TS']['codDeptoCad']}</lit:codDeptoCad>
			<lit:codUsuarioCad>{CONFIG['WS']['TS']['codUsuarioCad']}</lit:codUsuarioCad>
			<lit:codColigadaOpe>{CONFIG['WS']['TS']['codColigadaOpe']}</lit:codColigadaOpe>
			<lit:codAgenciaOpe>{CONFIG['WS']['TS']['codAgenciaOpe']}</lit:codAgenciaOpe>

			<lit:cnpjCpfFav>{cnpjCpfFav}</lit:cnpjCpfFav>
			<lit:tipPesFav>{CONFIG['WS']['fav']['tipPesFav']}</lit:tipPesFav>
			<lit:nomeFav>{CONFIG['WS']['fav']['nomeFav']}</lit:nomeFav>
			<lit:indCreditaCC>N</lit:indCreditaCC>
			<lit:tipoContaFav/>
			<lit:codBancoFav>{CONFIG['WS']['fav']['codBancoFav']}</lit:codBancoFav>
			<lit:codAgenciaFav/>
			<lit:dvAgenciaFav/>
			<lit:nroContaFav/>
			<lit:codIspbFav>{CONFIG['WS']['fav']['codIspbFav']}</lit:codIspbFav>

			<lit:cnpjCpfSac>{CONFIG['WS']['sac']['cnpjCpfSac']}</lit:cnpjCpfSac>
			<lit:tipPesSac>{CONFIG['WS']['sac']['tipPesSac']}</lit:tipPesSac>
			<lit:nomeSac>{CONFIG['WS']['sac']['nomeSac']}</lit:nomeSac>
			<lit:indDebitaCC>N</lit:indDebitaCC>
			<lit:tipoContaSac/>
			<lit:codBancoSac>{CONFIG['WS']['sac']['codBancoSac']}</lit:codBancoSac>
			<lit:codAgenciaSac/>
			<lit:dvAgenciaSac/>
			<lit:nroContaSac/>

			<lit:codCarteira>{CONFIG['WS']['TS']['STR0004']['codCarteira']}</lit:codCarteira>
			<lit:codEvento>{CONFIG['WS']['TS']['STR0004']['codEvento']}</lit:codEvento>
			<lit:complemento>{complemento}</lit:complemento>
			<lit:nroBordero>0000000</lit:nroBordero>
			<lit:indEmiteRecebe>E</lit:indEmiteRecebe>
			<lit:indMesmaTitularidade>N</lit:indMesmaTitularidade>
			<lit:vlrBruto>{vlrBruto}</lit:vlrBruto>
			<lit:vlrCPMFDespesa>0</lit:vlrCPMFDespesa>
			<lit:vlrRequisicao>{vlrBruto}</lit:vlrRequisicao>
			<lit:codFinalidade>5</lit:codFinalidade>
			<lit:codFinalidadeSPB>5</lit:codFinalidadeSPB>
			<lit:codBarras/>
			<lit:indPrevisao>N</lit:indPrevisao>
			<lit:codColigadaDes/>
			<lit:codAgenciaDes/>
			<lit:dtAgendt/>
			<lit:hrAgendt/>
			<lit:codFilial/>
		</lit:gerarRequisicao>
	</soap:Body>
</soap:Envelope>
    """

  # Send it
  payload = re.sub(r"\n[ \t]*", "", payload)
  assert ET.tostring(ET.fromstring(payload), encoding="unicode") != "", payload
  resp: Response = sendSoapRequest(
    CONFIG["WS"]["url_ABTSWS"],
    headers={
      "SOAPAction": "",
    },
    data=payload.encode("UTF-8"),
  )

  jsonResp: dict[str, Any] = xmltodict.parse(resp.text)
  jsonResp = jsonResp["soapenv:Envelope"]["soapenv:Body"]
  if "gerarRequisicaoResponse" not in jsonResp:
    return jsonResp["soapenv:Fault"]

  return jsonResp["gerarRequisicaoResponse"]["gerarRequisicaoReturn"]


def gerarRequisicao_STR0006(
  nroOrigem: str,
  vlrBruto: str,
  *,
  complemento: str,
  cnpjCpfFav: str,
  nroContaFav: str = "",
) -> dict[str, Any]:
  payload: str = f"""
<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/" xmlns:lit="http://literal.autbank.com.br">
	<soap:Body>
		<lit:gerarRequisicao>
			<lit:tipLiquidacao>{CONFIG['WS']['TS']['STR0006']['tipLiquidacao']}</lit:tipLiquidacao>
			<lit:datCadastro>{date.today().strftime(r'%d/%m/%Y')}</lit:datCadastro>
			<lit:datRequisicao>{date.today().strftime(r'%d/%m/%Y')}</lit:datRequisicao>
			<lit:datLiquidacao>{date.today().strftime(r'%d/%m/%Y')}</lit:datLiquidacao>
			<lit:datHoraLiquidacao>{date.today().strftime(r'%d/%m/%Y')} 00:00</lit:datHoraLiquidacao>

			<lit:codSisOrigem>{CONFIG['WS']['TS']['codSisOrigem']}</lit:codSisOrigem>
			<lit:nroOrigem>{nroOrigem}</lit:nroOrigem>
			<lit:codColigadaCad>{CONFIG['WS']['TS']['codColigadaCad']}</lit:codColigadaCad>
			<lit:codAgenciaCad>{CONFIG['WS']['TS']['codAgenciaCad']}</lit:codAgenciaCad>
			<lit:codDeptoCad>{CONFIG['WS']['TS']['codDeptoCad']}</lit:codDeptoCad>
			<lit:codUsuarioCad>{CONFIG['WS']['TS']['codUsuarioCad']}</lit:codUsuarioCad>
			<lit:codColigadaOpe>{CONFIG['WS']['TS']['codColigadaOpe']}</lit:codColigadaOpe>
			<lit:codAgenciaOpe>{CONFIG['WS']['TS']['codAgenciaOpe']}</lit:codAgenciaOpe>

			<lit:cnpjCpfFav>{cnpjCpfFav}</lit:cnpjCpfFav>
			<lit:tipPesFav>{CONFIG['WS']['fav']['tipPesFav']}</lit:tipPesFav>
			<lit:nomeFav>{CONFIG['WS']['fav']['nomeFav']}</lit:nomeFav>
			<lit:indCreditaCC>N</lit:indCreditaCC>
			<lit:tipoContaFav/>
			<lit:codBancoFav>{CONFIG['WS']['fav']['codBancoFav']}</lit:codBancoFav>
			<lit:codAgenciaFav/>
			<lit:dvAgenciaFav/>
			<lit:nroContaFav/>
			<lit:codIspbFav>{CONFIG['WS']['fav']['codIspbFav']}</lit:codIspbFav>

			<lit:cnpjCpfSac>{CONFIG['WS']['sac']['cnpjCpfSac']}</lit:cnpjCpfSac>
			<lit:tipPesSac>{CONFIG['WS']['sac']['tipPesSac']}</lit:tipPesSac>
			<lit:nomeSac>{CONFIG['WS']['sac']['nomeSac']}</lit:nomeSac>
			<lit:indDebitaCC>S</lit:indDebitaCC>
			<lit:tipoContaSac>CC</lit:tipoContaSac>
			<lit:codBancoSac>{CONFIG['WS']['sac']['codBancoSac']}</lit:codBancoSac>
			<lit:codAgenciaSac>{CONFIG['WS']['sac']['codAgenciaSac']}</lit:codAgenciaSac>
			<lit:dvAgenciaSac>{CONFIG['WS']['sac']['dvAgenciaSac']}</lit:dvAgenciaSac>
			<lit:nroContaSac>{CONFIG['WS']['sac']['nroContaSac']}</lit:nroContaSac>

			<lit:codCarteira>{CONFIG['WS']['TS']['STR0006']['codCarteira']}</lit:codCarteira>
			<lit:codEvento>{CONFIG['WS']['TS']['STR0006']['codEvento']}</lit:codEvento>
			<lit:complemento>{complemento}</lit:complemento>
			<lit:nroBordero>0000000</lit:nroBordero>
			<lit:indEmiteRecebe>E</lit:indEmiteRecebe>
			<lit:indMesmaTitularidade>N</lit:indMesmaTitularidade>
			<lit:vlrBruto>{vlrBruto}</lit:vlrBruto>
			<lit:vlrCPMFDespesa>0</lit:vlrCPMFDespesa>
			<lit:vlrRequisicao>{vlrBruto}</lit:vlrRequisicao>
			<lit:codFinalidade>5</lit:codFinalidade>
			<lit:codFinalidadeSPB>5</lit:codFinalidadeSPB>
			<lit:codBarras/>
			<lit:indPrevisao>N</lit:indPrevisao>
			<lit:codColigadaDes/>
			<lit:codAgenciaDes/>
			<lit:dtAgendt/>
			<lit:hrAgendt/>
			<lit:codFilial/>
		</lit:gerarRequisicao>
	</soap:Body>
</soap:Envelope>
    """

  # Send it
  payload = re.sub(r"\n[ \t]*", "", payload)
  assert ET.tostring(ET.fromstring(payload), encoding="unicode") != "", payload
  resp: Response = sendSoapRequest(
    CONFIG["WS"]["url_ABTSWS"],
    headers={
      "SOAPAction": "",
    },
    data=payload.encode("UTF-8"),
  )

  jsonResp: dict[str, Any] = xmltodict.parse(resp.text)
  jsonResp = jsonResp["soapenv:Envelope"]["soapenv:Body"]
  if "gerarRequisicaoResponse" not in jsonResp:
    return jsonResp["soapenv:Fault"]

  return jsonResp["gerarRequisicaoResponse"]["gerarRequisicaoReturn"]


def gerarRequisicao_STR0007(
  nroOrigem: str,
  vlrBruto: str,
  *,
  complemento: str,
  cnpjCpfFav: str,
  nroContaFav: str,
) -> dict[str, Any]:
  payload: str = f"""
<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/" xmlns:lit="http://literal.autbank.com.br">
	<soap:Body>
		<lit:gerarRequisicao>
			<lit:tipLiquidacao>{CONFIG['WS']['TS']['STR0007']['tipLiquidacao']}</lit:tipLiquidacao>
			<lit:datCadastro>{date.today().strftime(r'%d/%m/%Y')}</lit:datCadastro>
			<lit:datRequisicao>{date.today().strftime(r'%d/%m/%Y')}</lit:datRequisicao>
			<lit:datLiquidacao>{date.today().strftime(r'%d/%m/%Y')}</lit:datLiquidacao>
			<lit:datHoraLiquidacao>{date.today().strftime(r'%d/%m/%Y')} 00:00</lit:datHoraLiquidacao>

			<lit:codSisOrigem>{CONFIG['WS']['TS']['codSisOrigem']}</lit:codSisOrigem>
			<lit:nroOrigem>{nroOrigem}</lit:nroOrigem>
			<lit:codColigadaCad>{CONFIG['WS']['TS']['codColigadaCad']}</lit:codColigadaCad>
			<lit:codAgenciaCad>{CONFIG['WS']['TS']['codAgenciaCad']}</lit:codAgenciaCad>
			<lit:codDeptoCad>{CONFIG['WS']['TS']['codDeptoCad']}</lit:codDeptoCad>
			<lit:codUsuarioCad>{CONFIG['WS']['TS']['codUsuarioCad']}</lit:codUsuarioCad>
			<lit:codColigadaOpe>{CONFIG['WS']['TS']['codColigadaOpe']}</lit:codColigadaOpe>
			<lit:codAgenciaOpe>{CONFIG['WS']['TS']['codAgenciaOpe']}</lit:codAgenciaOpe>

			<lit:cnpjCpfFav>{cnpjCpfFav}</lit:cnpjCpfFav>
			<lit:tipPesFav>{CONFIG['WS']['fav']['tipPesFav']}</lit:tipPesFav>
			<lit:nomeFav>{CONFIG['WS']['fav']['nomeFav']}</lit:nomeFav>
			<lit:indCreditaCC>N</lit:indCreditaCC>
			<lit:tipoContaFav>CC</lit:tipoContaFav>
			<lit:codBancoFav>{CONFIG['WS']['fav']['codBancoFav']}</lit:codBancoFav>
			<lit:codAgenciaFav>{CONFIG['WS']['fav']['codAgenciaFav']}</lit:codAgenciaFav>
			<lit:dvAgenciaFav/>
			<lit:nroContaFav>{nroContaFav}</lit:nroContaFav>
			<lit:codIspbFav>{CONFIG['WS']['fav']['codIspbFav']}</lit:codIspbFav>

			<lit:cnpjCpfSac>{CONFIG['WS']['sac']['cnpjCpfSac']}</lit:cnpjCpfSac>
			<lit:tipPesSac>{CONFIG['WS']['sac']['tipPesSac']}</lit:tipPesSac>
			<lit:nomeSac>{CONFIG['WS']['sac']['nomeSac']}</lit:nomeSac>
			<lit:indDebitaCC>N</lit:indDebitaCC>
			<lit:tipoContaSac/>
			<lit:codBancoSac>{CONFIG['WS']['sac']['codBancoSac']}</lit:codBancoSac>
			<lit:codAgenciaSac/>
			<lit:dvAgenciaSac/>
			<lit:nroContaSac/>

			<lit:codCarteira>{CONFIG['WS']['TS']['STR0007']['codCarteira']}</lit:codCarteira>
			<lit:codEvento>{CONFIG['WS']['TS']['STR0007']['codEvento']}</lit:codEvento>
			<lit:complemento>{complemento}</lit:complemento>
			<lit:nroBordero>1325</lit:nroBordero>
			<lit:indEmiteRecebe>E</lit:indEmiteRecebe>
			<lit:indMesmaTitularidade>N</lit:indMesmaTitularidade>
			<lit:vlrBruto>{vlrBruto}</lit:vlrBruto>
			<lit:vlrCPMFDespesa>0</lit:vlrCPMFDespesa>
			<lit:vlrRequisicao>{vlrBruto}</lit:vlrRequisicao>
			<lit:codFinalidadeSPB>40</lit:codFinalidadeSPB>
			<lit:indPrevisao>N</lit:indPrevisao>
		</lit:gerarRequisicao>
	</soap:Body>
</soap:Envelope>
    """

  # Send it
  payload = re.sub(r"\n[ \t]*", "", payload)
  assert ET.tostring(ET.fromstring(payload), encoding="unicode") != "", payload
  resp: Response = sendSoapRequest(
    CONFIG["WS"]["url_ABTSWS"],
    headers={
      "SOAPAction": "",
    },
    data=payload.encode("UTF-8"),
  )

  jsonResp: dict[str, Any] = xmltodict.parse(resp.text)
  jsonResp = jsonResp["soapenv:Envelope"]["soapenv:Body"]
  if "gerarRequisicaoResponse" not in jsonResp:
    return jsonResp["soapenv:Fault"]

  return jsonResp["gerarRequisicaoResponse"]["gerarRequisicaoReturn"]


def gerarRequisicao_BLOQUETE(
  nroOrigem: str,
  vlrBruto: str,
  dda0110R1: dict[str, Any],
  *,
  complemento: str,
  cnpjCpfFav: str = "",
  nroContaFav: str = "",
  canalPagamento: str = "3",
) -> dict[str, Any]:
  assert canalPagamento in {"1", "2", "3", "4", "5", "6", "7", "8", "9"}
  payload: str = f"""
<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/" xmlns:lit="http://literal.autbank.com.br">
	<soap:Body>
		<lit:gerarRequisicao>
			<lit:tipLiquidacao>{CONFIG['WS']['TS']['BLOQUETE']['tipLiquidacao']}</lit:tipLiquidacao>
			<lit:datCadastro>{date.today().strftime(r'%d/%m/%Y')}</lit:datCadastro>
			<lit:datRequisicao>{date.today().strftime(r'%d/%m/%Y')}</lit:datRequisicao>
			<lit:datLiquidacao>{date.today().strftime(r'%d/%m/%Y')}</lit:datLiquidacao>
			<lit:datHoraLiquidacao>{date.today().strftime(r'%d/%m/%Y')} 00:00</lit:datHoraLiquidacao>

			<lit:codSisOrigem>{CONFIG['WS']['TS']['codSisOrigem']}</lit:codSisOrigem>
			<lit:nroOrigem>{nroOrigem}</lit:nroOrigem>
			<lit:codColigadaCad>{CONFIG['WS']['TS']['codColigadaCad']}</lit:codColigadaCad>
			<lit:codAgenciaCad>{CONFIG['WS']['TS']['codAgenciaCad']}</lit:codAgenciaCad>
			<lit:codDeptoCad>{CONFIG['WS']['TS']['codDeptoCad']}</lit:codDeptoCad>
			<lit:codUsuarioCad>{CONFIG['WS']['TS']['codUsuarioCad']}</lit:codUsuarioCad>
			<lit:codColigadaOpe>{CONFIG['WS']['TS']['codColigadaOpe']}</lit:codColigadaOpe>
			<lit:codAgenciaOpe>{CONFIG['WS']['TS']['codAgenciaOpe']}</lit:codAgenciaOpe>

			<lit:cnpjCpfFav>{dda0110R1['CNPJ_CPFBenfcrioOr']}</lit:cnpjCpfFav>
			<lit:tipPesFav>{dda0110R1['TpPessoaBenfcrioOr']}</lit:tipPesFav>
			<lit:nomeFav>{dda0110R1['Nom_RzSocBenfcrioOr']}</lit:nomeFav>
			<lit:indCreditaCC>N</lit:indCreditaCC>
			<lit:tipoContaFav>CC</lit:tipoContaFav>
			<lit:codBancoFav>{dda0110R1['CodPartDestinatario']}</lit:codBancoFav>
			<lit:codAgenciaFav/>
			<lit:dvAgenciaFav/>
			<lit:nroContaFav/>
			<lit:codIspbFav>{dda0110R1['ISPBPartDestinatario']}</lit:codIspbFav>

			<lit:cnpjCpfSac>{CONFIG['WS']['sac']['cnpjCpfSac']}</lit:cnpjCpfSac>
			<lit:tipPesSac>{CONFIG['WS']['sac']['tipPesSac']}</lit:tipPesSac>
			<lit:nomeSac>{CONFIG['WS']['sac']['nomeSac']}</lit:nomeSac>
			<lit:indDebitaCC>S</lit:indDebitaCC>
			<lit:tipoContaSac>CC</lit:tipoContaSac>
			<lit:codBancoSac>{CONFIG['WS']['sac']['codBancoSac']}</lit:codBancoSac>
			<lit:codAgenciaSac>{CONFIG['WS']['sac']['codAgenciaSac']}</lit:codAgenciaSac>
			<lit:dvAgenciaSac>{CONFIG['WS']['sac']['dvAgenciaSac']}</lit:dvAgenciaSac>
			<lit:nroContaSac>{CONFIG['WS']['sac']['nroContaSac']}</lit:nroContaSac>

			<lit:codBarras>{dda0110R1['NumCodBarras']}</lit:codBarras>
			<lit:vlrRequisicao>{vlrBruto}</lit:vlrRequisicao>
			<lit:vlrCPMFDespesa>0</lit:vlrCPMFDespesa>
			<lit:vlrBruto>{vlrBruto}</lit:vlrBruto>

			<lit:codCarteira>{CONFIG['WS']['TS']['BLOQUETE']['codCarteira']}</lit:codCarteira>
			<lit:codEvento>{CONFIG['WS']['TS']['BLOQUETE']['codEvento']}</lit:codEvento>
			<lit:complemento>{complemento}</lit:complemento>
			<lit:nroBordero>0000000</lit:nroBordero>
			<lit:indEmiteRecebe>E</lit:indEmiteRecebe>
			<lit:indMesmaTitularidade>N</lit:indMesmaTitularidade>
			<lit:codFinalidade>{canalPagamento}</lit:codFinalidade>
			<lit:codFinalidadeSPB>2</lit:codFinalidadeSPB>
			<lit:indPrevisao>N</lit:indPrevisao>
		</lit:gerarRequisicao>
	</soap:Body>
</soap:Envelope>
    """

  # Send it
  payload = re.sub(r"\n[ \t]*", "", payload)
  assert ET.tostring(ET.fromstring(payload), encoding="unicode") != "", payload
  resp: Response = sendSoapRequest(
    CONFIG["WS"]["url_ABTSWS"],
    headers={
      "SOAPAction": "",
    },
    data=payload.encode("UTF-8"),
  )

  jsonResp: dict[str, Any] = xmltodict.parse(resp.text)
  jsonResp = jsonResp["soapenv:Envelope"]["soapenv:Body"]
  if "gerarRequisicaoResponse" not in jsonResp:
    return jsonResp["soapenv:Fault"]

  return jsonResp["gerarRequisicaoResponse"]["gerarRequisicaoReturn"]


def gerarRequisicao_STR0026(
  nroOrigem: str,
  vlrBruto: str,
  dda0110R1: dict[str, Any],
  *,
  complemento: str,
  cnpjCpfFav: str = "",
  nroContaFav: str = "",
  canalPagamento: str = "3",
) -> dict[str, Any]:
  assert canalPagamento in {"1", "2", "3", "4", "5", "6", "7", "8", "9"}
  payload: str = f"""
<?xml version="1.0" encoding="utf-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:lit="http://literal.autbank.com.br">
	<soapenv:Header/>
	<soapenv:Body>
		<lit:gerarRequisicaoSTR0026PAG0122>
			<lit:tipLiquidacao>{CONFIG['WS']['TS']['STR0026']['tipLiquidacao']}</lit:tipLiquidacao>
			<lit:datCadastro>{date.today().strftime(r'%d/%m/%Y')}</lit:datCadastro>
			<lit:datRequisicao>{date.today().strftime(r'%d/%m/%Y')}</lit:datRequisicao>
			<lit:datLiquidacao>{date.today().strftime(r'%d/%m/%Y')}</lit:datLiquidacao>
			<lit:datHoraLiquidacao>{date.today().strftime(r'%d/%m/%Y')} 00:00</lit:datHoraLiquidacao>

			<lit:codSisOrigem>{CONFIG['WS']['TS']['codSisOrigem']}</lit:codSisOrigem>
			<lit:nroOrigem>{nroOrigem}</lit:nroOrigem>
			<lit:codColigadaCad>{CONFIG['WS']['TS']['codColigadaCad']}</lit:codColigadaCad>
			<lit:codAgenciaCad>{CONFIG['WS']['TS']['codAgenciaCad']}</lit:codAgenciaCad>
			<lit:codDeptoCad>{CONFIG['WS']['TS']['codDeptoCad']}</lit:codDeptoCad>
			<lit:codUsuarioCad>{CONFIG['WS']['TS']['codUsuarioCad']}</lit:codUsuarioCad>
			<lit:codColigadaOpe>{CONFIG['WS']['TS']['codColigadaOpe']}</lit:codColigadaOpe>
			<lit:codAgenciaOpe>{CONFIG['WS']['TS']['codAgenciaOpe']}</lit:codAgenciaOpe>

			<lit:cnpjCpfFav>{dda0110R1['CNPJ_CPFBenfcrioOr']}</lit:cnpjCpfFav>
			<lit:sequenciaFav>0</lit:sequenciaFav>
			<lit:tipPesFav>{dda0110R1['TpPessoaBenfcrioOr']}</lit:tipPesFav>
			<lit:nomeFav>{dda0110R1['Nom_RzSocBenfcrioOr']}</lit:nomeFav>
			<lit:codBancoFav>{dda0110R1['CodPartDestinatario']}</lit:codBancoFav>
			<lit:codIspbFav>{dda0110R1['ISPBPartDestinatario']}</lit:codIspbFav>
			<lit:codAgenciaFav/>
			<lit:dvAgenciaFav/>

			<lit:cnpjCpfCed>{dda0110R1['CNPJ_CPFBenfcrioOr']}</lit:cnpjCpfCed>
			<lit:tpPessoaCed>{dda0110R1['TpPessoaBenfcrioOr']}</lit:tpPessoaCed>

			<lit:cnpjCpfSac>{CONFIG['WS']['sac']['cnpjCpfSac']}</lit:cnpjCpfSac>
			<lit:tipPesSac>{CONFIG['WS']['sac']['tipPesSac']}</lit:tipPesSac>
			<lit:nomeSac>{CONFIG['WS']['sac']['nomeSac']}</lit:nomeSac>
			<lit:indDebitaCC>S</lit:indDebitaCC>
			<lit:codBancoSac>{CONFIG['WS']['sac']['codBancoSac']}</lit:codBancoSac>
			<lit:codAgenciaSac>{CONFIG['WS']['sac']['codAgenciaSac']}</lit:codAgenciaSac>
			<lit:dvAgenciaSac>{CONFIG['WS']['sac']['dvAgenciaSac']}</lit:dvAgenciaSac>
			<lit:codContaSac>{CONFIG['WS']['sac']['nroContaSac']}</lit:codContaSac>

			<lit:codBarras>{dda0110R1['NumCodBarras']}</lit:codBarras>
			<lit:vlrRequisicao>{vlrBruto}</lit:vlrRequisicao>
			<lit:vlrCPMFDespesa>0</lit:vlrCPMFDespesa>
			<lit:vlrBruto>{vlrBruto}</lit:vlrBruto>

			<lit:codBarras>{dda0110R1['NumCodBarras']}</lit:codBarras>
			<lit:tpDocBarras>1</lit:tpDocBarras>
			<lit:canPgto>{canalPagamento}</lit:canPgto>
			<lit:vlrDesctAbatt>0.00</lit:vlrDesctAbatt>
			<lit:vlrJuros>0.00</lit:vlrJuros>
			<lit:vlrMulta>0.00</lit:vlrMulta>
			<lit:vlrOtrAcresc>0.00</lit:vlrOtrAcresc>
			<lit:vlrRequisicao>{vlrBruto}</lit:vlrRequisicao>

			<lit:codCarteira>{CONFIG['WS']['TS']['BLOQUETE']['codCarteira']}</lit:codCarteira>
			<lit:codEvento>{CONFIG['WS']['TS']['BLOQUETE']['codEvento']}</lit:codEvento>
			<lit:complemento>{complemento}</lit:complemento>
			<lit:codIdentdTransf>{complemento}</lit:codIdentdTransf>
			<lit:nroBordero>1325</lit:nroBordero>
			<lit:nroBoleto/>
			<lit:indPrevisao>N</lit:indPrevisao>

			<lit:cnpjCpfPagFinal/>
			<lit:tipPesPagFinal/>
			<lit:nomePagFinal/>
		</lit:gerarRequisicaoSTR0026PAG0122>
	</soapenv:Body>
</soapenv:Envelope>
    """

  # Send it
  payload = re.sub(r"\n[ \t]*", "", payload)
  assert ET.tostring(ET.fromstring(payload), encoding="unicode") != "", payload
  resp: Response = sendSoapRequest(
    CONFIG["WS"]["url_ABTSWS"],
    headers={
      "SOAPAction": "",
    },
    data=payload.encode("UTF-8"),
  )

  jsonResp: dict[str, Any] = xmltodict.parse(resp.text)
  jsonResp = jsonResp["soapenv:Envelope"]["soapenv:Body"]
  if "gerarRequisicaoSTR0026PAG0122Response" not in jsonResp:
    return jsonResp["soapenv:Fault"]

  return jsonResp["gerarRequisicaoSTR0026PAG0122Response"]["gerarRequisicaoSTR0026PAG0122Return"]


################################
######## Main Function  ########
################################


def main(outputFile: TextIO, prettify: bool) -> None:
  """Main function"""

  with open('TestList.json', 'r') as f:
    testList: list[dict[str, str]] = json.load(f)
    del f

  # Main process
  outputJson: list[dict[str, Any]] = []
  respJson: dict[str, Any] = dict()
  dda0110R1: dict[str, Any] | None = None

  nroOrigem: int = int(CONFIG['WS']['TS']['ultimo_nroOrigem'])
  i: int = 0
  try:
    DEFAULT_V: dict[str, Any] = {
      "complemento": "",
      "cnpjCpfFav": "99999999999999",
      "nroContaFav": "99999999999999999999"
    }

    for (i, test) in enumerate(testList):
      dda0110R1 = None

      nroOrigem += 1
      testAux: dict[str, Any] = test.copy()
      if "codBarras" in testAux:
        del testAux["codBarras"]

      if "vlrBruto" in testAux:
        del testAux["vlrBruto"]

      del testAux["tipo"]

      for unknownKey in set(testAux.keys()).difference(DEFAULT_V.keys()):
        assert False, f"Key '{unknownKey}' is not part of the schema."

      testAux = {
        **DEFAULT_V,
        **testAux  # Completa o que falta em "testAux" com o DEFAULT_V
      }

      log.debug(f"Generating request with 'complemento':\n{test['complemento']}")
      vlrBruto: str = test.get("vlrBruto",
                               str(round(random.uniform(100, 1000), 2)))
      if test["tipo"] == "STR0004":
        respJson = gerarRequisicao_STR0004(f"{nroOrigem:020}", vlrBruto,
                                           **testAux)

      elif test["tipo"] == "STR0006":
        respJson = gerarRequisicao_STR0006(f"{nroOrigem:020}", vlrBruto,
                                           **testAux)

      elif test["tipo"] == "STR0007":
        respJson = gerarRequisicao_STR0007(f"{nroOrigem:020}", vlrBruto,
                                           **testAux)

      elif test["tipo"] == "BOLETO_NUCLEA":
        assert len(test.get("codBarras",
                            "")) >= 44, ("Property 'codBarras' missing or incomplete.")
        dda0110R1 = consultaTitulo2(test["codBarras"])
        if int(dda0110R1.get("SitTitPgto", "0")) != 12:
          log.info("Erro no serviço de consulta ou boleto não se encontra em aberto para pagamento!")
          continue

        if "vlrBruto" not in test:
          vlrBruto = calculaValorCobrar(dda0110R1)  # type: ignore
          if isinstance(vlrBruto, dict):
            raise ValueError(json.dumps(vlrBruto, ensure_ascii=False, indent=2))

        if float(vlrBruto) < 250_000:
          respJson = gerarRequisicao_BLOQUETE(f"{nroOrigem:020}", vlrBruto,
                                              dda0110R1, **testAux)
        else:
          respJson = gerarRequisicao_STR0026(f"{nroOrigem:020}", vlrBruto,
                                             dda0110R1, **testAux)

      else:
        assert False, "Undefined 'tipo'."

      log.debug(f"Request number: {respJson.get('nroRequisicao', None)}")
      outputJson.append({
        "complemento": test["complemento"],
        "vlrBruto": vlrBruto,
        "DDA0110R1": dda0110R1,
        "resp": respJson,
      })

  except Exception:
    log.warning(f"Error at test {i+1}:\n\n{traceback.format_exc()}")

  finally:
    CONFIG['WS']['TS']['ultimo_nroOrigem'] = str(nroOrigem)  # UPDATE 'nroOrigem'
    with open('TesourariaCrawler_gerarRequisicao_params.json', 'w') as f:
      json.dump(CONFIG, f, ensure_ascii=False, indent=2)
      del f

  # Save the output
  if prettify:
    json.dump(outputJson, outputFile, ensure_ascii=False, indent=2)
  else:
    json.dump(outputJson, outputFile, ensure_ascii=False, separators=(',', ':'))


################################
############# CLI  #############
################################

# Runs the program
if __name__ == "__main__":
  try:
    argParser: ArgumentParser = ArgumentParser(
      description="Arbi Crawler for: Consulta Titulo.")

    # Parameter parsedArgs.outputFile
    _ = argParser.add_argument(
      "-o", "--output", type=FileType("w", encoding="UTF-8"), required=False,
      default="output.json",
      help="Arquivo de saída JSON (UTF-8). Deve ser gravável.",
      metavar="outputFileName", dest="outputFile")

    parsedArgs: Namespace = argParser.parse_args()

    # Main call
    logName: str = join(getcwd(),
                        f"log_{date.today().strftime('%Y-%m-%d')}.txt")

    with open(logName, "a+", encoding="UTF-8") as logFile:
      log.basicConfig(stream=logFile, encoding="UTF-8", level=log.DEBUG,
                      format="%(asctime)s|%(levelname)s|%(message)s",
                      datefmt="%Y-%m-%d %H:%M:%S")

      with redirect_stdout(logFile):
        with redirect_stderr(logFile):
          try:
            log.debug("################")
            log.debug(f"Program started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}.")

            # Call the main function
            main(parsedArgs.outputFile, prettify=True)

            log.debug(f"Finished run at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}.")

          except BaseException:
            log.warning(f"Unexpected error happened:\n\n{traceback.format_exc()}")
            exit(1)

  except SystemExit as e:
    raise e

  except BaseException:
    log.warning(f"Unexpected error happened:\n\n{traceback.format_exc()}")
    exit(1)
