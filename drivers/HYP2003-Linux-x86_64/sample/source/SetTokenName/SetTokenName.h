#ifndef SETTOKENNAME_H
#define SETTOKENNAME_H

#include "../../include/auxiliary.h"
#include <iostream>
using namespace std;
class SetTokenName
{
public:
	SetTokenName();
	~SetTokenName();
	CK_RV Connect();
	CK_RV Set(string);
protected:
	void *m_hPkiLib;
	AUX_FUNC_LIST_PTR m_pAuxFunc;
	CK_SLOT_ID_PTR m_pSlotList;
};

#endif
