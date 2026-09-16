#include <iostream>
#include <dlfcn.h>
#include <stdio.h>
#include <string.h>
#include "../../include/cryptoki_ext.h"
#include "../../include/auxiliary.h"
#include "SetTimer.h"

using namespace std;

SetTimer::SetTimer()
{
	m_hPkiLib = NULL;
}
SetTimer::~SetTimer()
{
	if(m_pSlotList != NULL) delete[] m_pSlotList;
}

CK_RV SetTimer::Connect()
{
	CK_RV rv;
	rv = C_Initialize(NULL_PTR);
	if(CKR_OK != rv)
	{
		cout<<"Initialize PKCS#11 fault"<<endl;
		return rv;
	}
	CK_ULONG ulCount;
	rv = C_GetSlotList(TRUE, NULL_PTR, &ulCount);
	if(CKR_OK != rv)
	{
		cout<<"Get slot list fault"<<endl;
		return rv;
	}
	if(0 >= ulCount)
	{
		cout<<"Make sure you have inserted token"<<endl;
		return CKR_GENERAL_ERROR;
	}
	m_pSlotList = (CK_SLOT_ID_PTR)new CK_SLOT_ID[ulCount];
	if(NULL == m_pSlotList)
	{
		cout<<"Can't allocate enough memeroy"<<endl;
		return CKR_GENERAL_ERROR;
	}
	rv = C_GetSlotList(TRUE, m_pSlotList, &ulCount);
	if(CKR_OK != rv)
	{
		cout<<"Can't get slot list"<<endl;
		return rv;
	}else {
		cout<<"Connect OK!"<<endl;
		return rv;
	}

}
CK_RV SetTimer::Set(CK_ULONG ulTimer)
{
	CK_RV rv;
	char p11Name[100]={0};
	char *sysCmd="cut -f2 -d= ../Rule.mak";
	FILE *fd;
	int retNum=0;
	if((fd=popen(sysCmd, "r"))> (FILE *)0)
	{
		retNum = fread(p11Name,sizeof(char),sizeof(p11Name),fd);
		if(retNum <= 0)
		{
			printf("read p11 name error\n");
			return CKR_GENERAL_ERROR;
		}
		if(p11Name[retNum-1] == '\n')
		{
			p11Name[retNum-1] = 0;
		}

	}
	m_hPkiLib = dlopen(p11Name, RTLD_NOW);
	if(NULL_PTR == m_hPkiLib)
	{
		cout<<"Can't load lib \"libcastle_v2.so.1.0.0\""<<endl;
		return CKR_GENERAL_ERROR;
	}
	EP_GetAuxFunctionList pE_GetAuxFunctionList = (EP_GetAuxFunctionList)dlsym(m_hPkiLib,"E_GetAuxFunctionList");
	if(NULL_PTR == pE_GetAuxFunctionList)
	{
		dlclose(m_hPkiLib);
		cout<<"Can't get function list"<<endl;
		return CKR_GENERAL_ERROR;
	}
	rv = pE_GetAuxFunctionList(&m_pAuxFunc);
	if(CKR_OK != rv)
	{
		dlclose(m_hPkiLib);
		cout<<"Can't get function list"<<endl;
		return CKR_GENERAL_ERROR;
	}
	rv = ((EP_SetTokenTimeout)(m_pAuxFunc->pFunc[EP_SET_TOKEN_TIMEOUT]))(m_pSlotList[0],ulTimer * 1000 );
	if(CKR_OK != rv)
	{
		dlclose(m_hPkiLib);
		cout<<"Set timer fault"<<endl;
		return rv;
	} else {
		cout<<"Set timer successfully"<<endl;
		dlclose(m_hPkiLib);
		return rv;
	}

}
