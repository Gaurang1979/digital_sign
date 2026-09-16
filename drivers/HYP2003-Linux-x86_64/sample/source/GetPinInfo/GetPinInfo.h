#ifndef GETPININFO_H
#define GETPININFO_H

#include "../../include/auxiliary.h"

class GetPinInfo
{
public:
	GetPinInfo();
	~GetPinInfo();
	CK_RV Connect();
	CK_RV Get();
protected:
	void *m_hPkiLib;
	AUX_PIN_INFO_PTR m_pPinInfo;
	AUX_FUNC_LIST_PTR m_pAuxFunc;
	CK_SLOT_ID_PTR m_pSlotList;
};

#endif
